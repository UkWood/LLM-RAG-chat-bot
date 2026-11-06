"""Explicit trusted local artifact import; never downloads models or approves KB sources."""
import ctypes
import errno
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import stat
import tempfile
from urllib.parse import urlsplit

from ..ingestion.registry import unique_object, _hash
from .embeddings import LocalONNXEncoder
from .dense import normalized

RUNTIME_FIELDS={'schema_version','model_id','revision','dimensions','max_length','query_prefix','passage_prefix',
                'pad_id','output_name','pooling'}
PROFILE_FIELDS=RUNTIME_FIELDS|{'source_url','license_id','review_reference','purpose'}
LIMITS={'model.onnx':2_000_000_000,'tokenizer.json':20_000_000,'MODEL_CARD.md':1_000_000,'LICENSE':256_000}
HASH_FIELDS={'model.onnx':'model_sha256','tokenizer.json':'tokenizer_sha256',
             'MODEL_CARD.md':'model_card_sha256','LICENSE':'license_sha256'}


def _digest(*parts):
    return sha256(json.dumps(parts,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def _json(raw):
    if not isinstance(raw,bytes) or len(raw)>16000:
        raise ValueError('Metadata size/type limit')
    value=json.loads(raw,object_pairs_hook=unique_object)
    if not isinstance(value,dict):raise ValueError('Expected metadata object')
    return value


def _profile(raw):
    data=_json(raw)
    if (set(data)!=PROFILE_FIELDS or type(data['schema_version']) is not int or data['schema_version']!=1
            or not isinstance(data['model_id'],str) or not re.fullmatch(r'[A-Za-z0-9._-]+/[A-Za-z0-9._-]+',data['model_id'])
            or any(part in ('.','..') for part in data['model_id'].split('/')) or not _hash(data['revision'],40)
            or data['purpose'] not in ('semantic_candidate','runtime_contract')
            or type(data['dimensions']) is not int or not 1<=data['dimensions']<=8192
            or type(data['max_length']) is not int or not 1<=data['max_length']<=512
            or type(data['pad_id']) is not int or data['pad_id']<0 or data['pooling']!='mean'):
        raise ValueError('Invalid explicit model profile')
    for key in ('query_prefix','passage_prefix','output_name','source_url','license_id','review_reference'):
        if not isinstance(data[key],str) or len(data[key])>2000:
            raise ValueError('Invalid profile string')
    if any(not data[key].strip() for key in ('output_name','source_url','license_id','review_reference')):
        raise ValueError('Missing model-card/license review provenance')
    if (not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9.+-]{1,79}',data['license_id'])
            or data['license_id'].upper() in {'UNKNOWN','UNVERIFIED','NOASSERTION','NONE'}):
        raise ValueError('Explicit reviewed license identifier required')
    url=urlsplit(data['source_url'])
    if (url.scheme!='https' or url.netloc not in ('huggingface.co','github.com') or url.query or url.fragment
            or data['source_url']!=data['source_url'].strip()
            or url.path!=f'/{data["model_id"]}/tree/{data["revision"]}'):
        raise ValueError('Source URL must pin exact public repo/revision')
    return data


def _read(path,maximum):
    path=Path(path)
    if path.is_symlink():raise ValueError('Artifact symlinks are not accepted')
    flags=os.O_RDONLY|getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_NONBLOCK',0)
    descriptor=os.open(path,flags)
    with os.fdopen(descriptor,'rb') as file:
        info=os.fstat(file.fileno())
        if not stat.S_ISREG(info.st_mode) or not 0<info.st_size<=maximum:
            raise ValueError('Artifact must be bounded nonempty regular file')
        data=file.read(maximum+1)
    if not data or len(data)>maximum:raise ValueError('Artifact size limit')
    return data


def _write_json(path,data):
    path.write_text(json.dumps(data,ensure_ascii=False,sort_keys=True,indent=2)+'\n')


def _manifest(profile,hashes):
    return dict({key:profile[key] for key in sorted(RUNTIME_FIELDS)},model_sha256=hashes['model_sha256'],
                tokenizer_sha256=hashes['tokenizer_sha256'])


def _publish_new_directory(staging,destination):
    # Linux CPU profile: atomic no-replace, including a concurrently created target.
    libc=ctypes.CDLL(None,use_errno=True)
    rename=getattr(libc,'renameat2',None)
    if rename is None:raise OSError(errno.ENOSYS,'Atomic no-replace publication unavailable')
    rename.argtypes=[ctypes.c_int,ctypes.c_char_p,ctypes.c_int,ctypes.c_char_p,ctypes.c_uint]
    rename.restype=ctypes.c_int
    if rename(-100,os.fsencode(staging),-100,os.fsencode(destination),1)!=0:
        code=ctypes.get_errno();raise OSError(code,os.strerror(code),str(destination))


def prepare_local_model(profile_raw,model_path,tokenizer_path,card_path,license_path,destination):
    profile=_profile(profile_raw)
    destination=Path(destination)
    if destination.name in ('','.','..'):raise ValueError('Invalid destination')
    parent=destination.parent.resolve();target=parent/destination.name
    if target.exists() or target.is_symlink():raise FileExistsError('Existing destination is never replaced')
    artifacts={name:_read(path,LIMITS[name]) for name,path in zip(LIMITS,(model_path,tokenizer_path,card_path,license_path))}
    for name in ('MODEL_CARD.md','LICENSE'):
        if not artifacts[name].decode('utf-8').strip():raise ValueError('Empty model-card/license text')
    hashes={HASH_FIELDS[name]:sha256(data).hexdigest() for name,data in artifacts.items()}
    manifest=_manifest(profile,hashes)
    bundle_id=_digest('local-model-bundle-v1',profile,hashes)
    provenance=dict(schema_version=1,bundle_id=bundle_id,profile=profile,**hashes,semantic_quality='not_measured')
    parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.embedding-staging-',dir=parent) as temp:
        staging=Path(temp)
        for name,data in artifacts.items():(staging/name).write_bytes(data)
        _write_json(staging/'manifest.json',manifest);_write_json(staging/'provenance.json',provenance)
        encoder=LocalONNXEncoder(staging)
        expected_identity=dict(kind='local_onnx',**manifest)
        if encoder.identity!=expected_identity:raise ValueError('Loaded model identity differs from imported bytes')
        query=normalized(encoder.encode_query('synthetic query'),profile['dimensions'])
        passages=encoder.encode_documents(['synthetic passage'])
        if len(passages)!=1:raise ValueError('Smoke passage batch mismatch')
        passage=normalized(passages[0],profile['dimensions'])
        repeated=normalized(encoder.encode_query('synthetic query'),profile['dimensions'])
        if any(abs(a-b)>1e-6 for a,b in zip(query,repeated)):raise ValueError('Nondeterministic query smoke')
        smoke=dict(schema_version=1,bundle_id=bundle_id,inference_smoke='passed',dimensions=profile['dimensions'],
                   model_identity_sha256=_digest(expected_identity),manifest_sha256=sha256((staging/'manifest.json').read_bytes()).hexdigest(),
                   smoke_vector_sha256=_digest(query,passage),semantic_quality='not_measured',
                   eligible_for_candidate_benchmark=profile['purpose']=='semantic_candidate')
        _write_json(staging/'smoke.json',smoke)
        read_model_provenance(staging,require_semantic=False)
        _publish_new_directory(staging,target)
    return smoke


def read_model_provenance(directory,*,require_semantic=True,identity=None):
    directory=Path(directory)
    try:
        provenance=_json(_read(directory/'provenance.json',16000))
        expected={'schema_version','bundle_id','profile','semantic_quality',*HASH_FIELDS.values()}
        if set(provenance)!=expected or type(provenance['schema_version']) is not int or provenance['schema_version']!=1:
            raise ValueError('Invalid provenance contract')
        profile=_profile(json.dumps(provenance['profile']).encode())
        if require_semantic and profile['purpose']!='semantic_candidate':
            raise ValueError('Runtime-contract artifact cannot be used for semantic quality evaluation')
        hashes={key:provenance[key] for key in HASH_FIELDS.values()}
        if any(not _hash(value) for value in hashes.values()) or provenance['bundle_id']!=_digest('local-model-bundle-v1',profile,hashes):
            raise ValueError('Model bundle identity mismatch')
        if provenance['semantic_quality']!='not_measured':raise ValueError('Import cannot attest model quality')
        manifest_raw=_read(directory/'manifest.json',16000);manifest=_json(manifest_raw)
        if manifest!=_manifest(profile,hashes):raise ValueError('Manifest/provenance mismatch')
        if identity is not None and identity!=dict(kind='local_onnx',**manifest):raise ValueError('Runtime identity differs from provenance')
        for name,key in HASH_FIELDS.items():
            if sha256(_read(directory/name,LIMITS[name])).hexdigest()!=hashes[key]:raise ValueError('Prepared artifact drift')
        smoke=_json(_read(directory/'smoke.json',16000))
        smoke_fields={'schema_version','bundle_id','inference_smoke','dimensions','model_identity_sha256','manifest_sha256',
                      'smoke_vector_sha256','semantic_quality','eligible_for_candidate_benchmark'}
        if (set(smoke)!=smoke_fields or type(smoke['schema_version']) is not int or smoke['schema_version']!=1
                or smoke['bundle_id']!=provenance['bundle_id'] or smoke['inference_smoke']!='passed'
                or type(smoke['dimensions']) is not int or smoke['dimensions']!=profile['dimensions']
                or smoke['model_identity_sha256']!=_digest(dict(kind='local_onnx',**manifest))
                or smoke['manifest_sha256']!=sha256(manifest_raw).hexdigest() or not _hash(smoke['smoke_vector_sha256'])
                or smoke['semantic_quality']!='not_measured' or type(smoke['eligible_for_candidate_benchmark']) is not bool
                or smoke['eligible_for_candidate_benchmark']!=(profile['purpose']=='semantic_candidate')):
            raise ValueError('Smoke receipt mismatch')
        return provenance
    except (OSError,KeyError,TypeError,UnicodeError):
        raise ValueError('Prepared checkpoint provenance unavailable or malformed') from None
