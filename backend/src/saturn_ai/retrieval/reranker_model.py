"""Explicit pinned local single-logit pair scorer; never downloads or pools vectors."""
from hashlib import sha256
import json
from pathlib import Path
import re
import tempfile
from urllib.parse import urlsplit
import numpy as np

from ..ingestion.registry import _hash
from .model_preparation import (_json, _read, _digest, _write_json, _publish_new_directory, LIMITS, HASH_FIELDS)
from .embeddings import _load_runtime
from .reranking import validate_pairs, checked_scores

PROFILE_FIELDS={'schema_version','kind','model_id','revision','source_url','license_id','review_reference',
                'purpose','max_length','pad_id','output_name','activation'}


def _profile(raw):
    p=_json(raw)
    if (set(p)!=PROFILE_FIELDS or type(p['schema_version']) is not int or p['schema_version']!=1
            or p['kind']!='local_onnx_pair_scorer' or p['activation']!='identity'
            or p['purpose'] not in ('semantic_candidate','runtime_contract')
            or type(p['max_length']) is not int or not 1<=p['max_length']<=512
            or type(p['pad_id']) is not int or p['pad_id']<0
            or not isinstance(p['model_id'],str) or not re.fullmatch(r'[A-Za-z0-9._-]+/[A-Za-z0-9._-]+',p['model_id'])
            or any(x in ('.','..') for x in p['model_id'].split('/')) or not _hash(p['revision'],40)):
        raise ValueError('Invalid pair model profile')
    for key in ('source_url','license_id','review_reference','output_name'):
        if not isinstance(p[key],str) or not p[key].strip() or len(p[key])>2000:
            raise ValueError('Explicit pair model review provenance required')
    if (not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9.+-]{1,79}',p['license_id'])
            or p['license_id'].upper() in {'UNKNOWN','UNVERIFIED','NOASSERTION','NONE'}):
        raise ValueError('Reviewed license assertion required')
    url=urlsplit(p['source_url'])
    if (url.netloc not in ('huggingface.co','github.com')
            or p['source_url']!=f'https://{url.netloc}/{p["model_id"]}/tree/{p["revision"]}'):
        raise ValueError('Canonical pinned source URL required')
    return p


def _manifest(profile,hashes):return dict(profile,**hashes)


def _read_manifest(directory):
    manifest=_json(_read(directory/'manifest.json',16000))
    if set(manifest)!=PROFILE_FIELDS|set(HASH_FIELDS.values()):raise ValueError('Invalid pair manifest schema')
    profile=_profile(json.dumps({key:manifest[key] for key in PROFILE_FIELDS}).encode())
    hashes={key:manifest[key] for key in HASH_FIELDS.values()}
    if any(not _hash(value) for value in hashes.values()):raise ValueError('Invalid artifact hashes')
    artifacts={name:_read(directory/name,LIMITS[name]) for name in LIMITS}
    for name,key in HASH_FIELDS.items():
        if sha256(artifacts[name]).hexdigest()!=hashes[key]:raise ValueError('Pair artifact hash drift')
    for name in ('MODEL_CARD.md','LICENSE'):
        if not artifacts[name].decode('utf-8').strip():raise ValueError('Empty review evidence')
    return manifest,profile,hashes,artifacts


class LocalONNXReranker:
    def __init__(self,directory):
        manifest,_,_,artifacts=_read_manifest(Path(directory))
        self._identity=manifest
        self._tokenizer,self._session=_load_runtime(artifacts['model.onnx'],artifacts['tokenizer.json'],manifest)
        from tokenizers import Tokenizer
        self._length_tokenizer=Tokenizer.from_str(artifacts['tokenizer.json'].decode())
        self._length_tokenizer.no_truncation();self._length_tokenizer.no_padding()
        self._tokenizer.enable_truncation(max_length=manifest['max_length'],strategy='longest_first')
        pad_token=self._tokenizer.id_to_token(manifest['pad_id'])
        if pad_token is None:raise ValueError('Padding token missing from tokenizer')
        self._tokenizer.enable_padding(pad_id=manifest['pad_id'],pad_token=pad_token)
        inputs=self._session.get_inputs()
        if (not {'input_ids','attention_mask'}<={i.name for i in inputs}
                or not {i.name for i in inputs}<={'input_ids','attention_mask','token_type_ids'}
                or any(i.type not in ('tensor(int64)','tensor(int32)') for i in inputs)):
            raise ValueError('Unsupported pair model input contract')

    @property
    def identity(self):return dict(self._identity)

    def pair_lengths(self,query,passages):
        validate_pairs(query,passages)
        return [len(e.ids) for e in self._length_tokenizer.encode_batch([(query,p) for p in passages])]

    def score_pairs(self,query,passages):
        validate_pairs(query,passages)
        result=[]
        for start in range(0,len(passages),8):
            batch=passages[start:start+8]
            encodings=self._tokenizer.encode_batch([(query,p) for p in batch])
            if len(encodings)!=len(batch):raise ValueError('Pair tokenization batch mismatch')
            values=dict(input_ids=np.asarray([e.ids for e in encodings],dtype=np.int64),
                        attention_mask=np.asarray([e.attention_mask for e in encodings],dtype=np.int64),
                        token_type_ids=np.asarray([e.type_ids for e in encodings],dtype=np.int64))
            if (values['input_ids'].ndim!=2 or not 0<values['input_ids'].shape[1]<=self._identity['max_length']
                    or not np.isin(values['attention_mask'],[0,1]).all()
                    or (values['attention_mask'].sum(axis=1)==0).any()):
                raise ValueError('Invalid pair tokenization shape/mask')
            feed={i.name:values[i.name].astype(np.int64 if i.type=='tensor(int64)' else np.int32)
                  for i in self._session.get_inputs()}
            raw=self._session.run([self._identity['output_name']],feed)[0]
            if raw.shape!=(len(batch),1) or not np.isfinite(raw).all():
                raise ValueError('Expected finite single-logit [batch,1] pair output')
            result.extend(float(value) for value in raw[:,0])
        return checked_scores(result,len(passages))


def prepare_local_reranker(profile_raw,model_path,tokenizer_path,card_path,license_path,destination):
    profile=_profile(profile_raw);destination=Path(destination)
    if destination.name in ('','.','..'):raise ValueError('Invalid destination')
    parent=destination.parent.resolve();target=parent/destination.name
    if target.exists() or target.is_symlink():raise FileExistsError('Existing destination is never replaced')
    artifacts={name:_read(path,LIMITS[name]) for name,path in zip(LIMITS,(model_path,tokenizer_path,card_path,license_path))}
    hashes={HASH_FIELDS[name]:sha256(value).hexdigest() for name,value in artifacts.items()}
    manifest=_manifest(profile,hashes)
    provenance=dict(schema_version=1,bundle_id=_digest('pair-model-bundle-v1',profile,hashes),
                    profile=profile,**hashes,semantic_quality='not_measured')
    parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.reranker-staging-',dir=parent) as temp:
        staging=Path(temp)
        for name,value in artifacts.items():(staging/name).write_bytes(value)
        _write_json(staging/'manifest.json',manifest);_write_json(staging/'provenance.json',provenance)
        scorer=LocalONNXReranker(staging)
        if scorer.identity!=manifest:raise ValueError('Runtime identity differs from imported bytes')
        first=scorer.score_pairs('synthetic query',['synthetic passage','another synthetic passage'])
        second=scorer.score_pairs('synthetic query',['synthetic passage','another synthetic passage'])
        if any(abs(a-b)>1e-6 for a,b in zip(first,second)):raise ValueError('Nondeterministic pair smoke')
        smoke=dict(schema_version=1,bundle_id=provenance['bundle_id'],inference_smoke='passed',
            score_sha256=_digest(first),manifest_sha256=sha256((staging/'manifest.json').read_bytes()).hexdigest(),
            semantic_quality='not_measured',eligible_for_candidate_benchmark=profile['purpose']=='semantic_candidate')
        _write_json(staging/'smoke.json',smoke)
        read_reranker_provenance(staging,require_semantic=False)
        _publish_new_directory(staging,target)
    return smoke


def read_reranker_provenance(directory,*,require_semantic=True,identity=None):
    directory=Path(directory)
    try:
        manifest,profile,hashes,_=_read_manifest(directory)
        provenance=_json(_read(directory/'provenance.json',16000))
        expected=dict(schema_version=1,bundle_id=_digest('pair-model-bundle-v1',profile,hashes),
                      profile=profile,**hashes,semantic_quality='not_measured')
        if provenance!=expected or type(provenance.get('schema_version')) is not int:
            raise ValueError('Pair provenance mismatch')
        if require_semantic and profile['purpose']!='semantic_candidate':raise ValueError('Runtime-contract pair graph is not semantic quality')
        if identity is not None and manifest!=identity:raise ValueError('Loaded pair identity mismatch')
        smoke=_json(_read(directory/'smoke.json',16000))
        smoke_fields={'schema_version','bundle_id','inference_smoke','score_sha256','manifest_sha256',
                      'semantic_quality','eligible_for_candidate_benchmark'}
        if (set(smoke)!=smoke_fields or type(smoke['schema_version']) is not int or smoke['schema_version']!=1
                or smoke['bundle_id']!=expected['bundle_id'] or smoke['inference_smoke']!='passed'
                or not _hash(smoke['score_sha256']) or smoke['semantic_quality']!='not_measured'
                or smoke['manifest_sha256']!=sha256(_read(directory/'manifest.json',16000)).hexdigest()
                or type(smoke['eligible_for_candidate_benchmark']) is not bool
                or smoke['eligible_for_candidate_benchmark']!=(profile['purpose']=='semantic_candidate')):
            raise ValueError('Invalid pair smoke receipt')
        return provenance
    except (OSError,TypeError,KeyError,UnicodeError):
        raise ValueError('Prepared pair bundle unavailable or malformed') from None


def load_semantic_reranker(directory):
    before=read_reranker_provenance(directory)
    scorer=LocalONNXReranker(directory)
    after=read_reranker_provenance(directory,identity=scorer.identity)
    if before!=after:raise ValueError('Pair bundle changed during loading')
    return scorer,after
