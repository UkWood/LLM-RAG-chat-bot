"""Optional owner-provisioned local ONNX encoder. No automatic model download."""
from hashlib import sha256
import json
from pathlib import Path
from typing import Protocol
import numpy as np
from ..ingestion.registry import unique_object, _hash
from .dense import normalized


class Encoder(Protocol):
    dimensions: int
    identity: dict
    def encode_documents(self, texts: list[str]) -> list[list[float]]: ...
    def encode_query(self, text: str) -> list[float]: ...


def pool_embeddings(hidden, mask, *, dimensions):
    hidden, mask = np.asarray(hidden), np.asarray(mask)
    if (hidden.ndim != 3 or mask.ndim != 2 or hidden.shape[:2] != mask.shape or hidden.shape[2] != dimensions
            or not np.isfinite(hidden).all() or not np.isin(mask, [0,1]).all() or (mask.sum(axis=1) == 0).any()):
        raise ValueError('Invalid hidden-state/mask shape or values')
    pooled = (hidden * mask[...,None]).sum(axis=1) / mask.sum(axis=1)[...,None]
    return [list(normalized(vector, dimensions)) for vector in pooled]


def _load_runtime(directory, manifest):
    try:
        import onnxruntime as ort
        from tokenizers import Tokenizer
    except ImportError:
        raise ValueError('Install requirements-onnx.lock for local neural inference') from None
    tokenizer = Tokenizer.from_file(str(directory/'tokenizer.json'))
    tokenizer.enable_truncation(max_length=manifest['max_length'])
    tokenizer.enable_padding(pad_id=manifest['pad_id'])
    options = ort.SessionOptions()
    options.intra_op_num_threads = 1
    options.inter_op_num_threads = 1
    session = ort.InferenceSession(str(directory/'model.onnx'), sess_options=options, providers=['CPUExecutionProvider'])
    if manifest['output_name'] not in {o.name for o in session.get_outputs()}:
        raise ValueError('Configured output absent from local ONNX graph')
    return tokenizer, session


class LocalONNXEncoder:
    """Single-file trusted model only; not an untrusted-upload parser/sandbox."""
    def __init__(self, directory: Path):
        directory = directory.resolve()
        raw = (directory/'manifest.json').read_bytes()
        if len(raw) > 16000:
            raise ValueError('Model manifest size limit')
        manifest = json.loads(raw, object_pairs_hook=unique_object)
        fields = {'schema_version','model_id','revision','dimensions','max_length','query_prefix','passage_prefix',
                  'pad_id','output_name','pooling','model_sha256','tokenizer_sha256'}
        if (not isinstance(manifest, dict) or set(manifest) != fields or type(manifest['schema_version']) is not int
                or manifest['schema_version'] != 1 or type(manifest['dimensions']) is not int
                or not 1 <= manifest['dimensions'] <= 8192 or type(manifest['max_length']) is not int
                or not 1 <= manifest['max_length'] <= 512 or type(manifest['pad_id']) is not int
                or manifest['pad_id'] < 0 or manifest['pooling'] != 'mean'
                or any(not isinstance(manifest[k], str) for k in ('model_id','revision','query_prefix','passage_prefix','output_name'))
                or any(not manifest[k].strip() for k in ('model_id','revision','output_name'))):
            raise ValueError('Invalid local ONNX configuration')
        for filename, field, maximum in [('model.onnx','model_sha256',2_000_000_000),
                                          ('tokenizer.json','tokenizer_sha256',20_000_000)]:
            path = (directory/filename).resolve()
            if not path.is_relative_to(directory) or not path.is_file() or path.stat().st_size > maximum or not _hash(manifest[field]):
                raise ValueError('Invalid or escaping local artifact')
            digest = sha256()
            with path.open('rb') as file:
                for block in iter(lambda: file.read(1024*1024), b''):
                    digest.update(block)
            if digest.hexdigest() != manifest[field]:
                raise ValueError('Local model/tokenizer hash drift')
        self.dimensions = manifest['dimensions']
        self.identity = dict(kind='local_onnx', **manifest)
        self._manifest = manifest
        self._tokenizer, self._session = _load_runtime(directory, manifest)
        if not {i.name for i in self._session.get_inputs()} <= {'input_ids','attention_mask','token_type_ids'}:
            raise ValueError('Unsupported model input contract')

    def _encode(self, texts, prefix):
        if not isinstance(texts, list) or any(not isinstance(t, str) or not t.strip() or len(t)>20000 for t in texts):
            raise ValueError('Invalid embedding text batch')
        result = []
        for start in range(0, len(texts), 16):
            batch = texts[start:start+16]
            encodings = self._tokenizer.encode_batch([prefix+t for t in batch])
            if len(encodings) != len(batch):
                raise ValueError('Tokenizer batch mismatch')
            values = dict(input_ids=np.array([e.ids for e in encodings],dtype=np.int64),
                          attention_mask=np.array([e.attention_mask for e in encodings],dtype=np.int64),
                          token_type_ids=np.array([e.type_ids for e in encodings],dtype=np.int64))
            if values['input_ids'].ndim != 2 or values['input_ids'].shape[1] > self._manifest['max_length']:
                raise ValueError('Tokenizer sequence limit')
            inputs = {}
            for item in self._session.get_inputs():
                if item.type not in ('tensor(int64)','tensor(int32)'):
                    raise ValueError('Unsupported ONNX input type')
                inputs[item.name] = values[item.name].astype(np.int64 if item.type=='tensor(int64)' else np.int32)
            outputs = self._session.run([self._manifest['output_name']], inputs)
            pooled = pool_embeddings(outputs[0], values['attention_mask'], dimensions=self.dimensions)
            if len(pooled) != len(batch):
                raise ValueError('Model output batch mismatch')
            result.extend(pooled)
        return result

    def encode_documents(self, texts):
        return self._encode(texts, self._manifest['passage_prefix'])

    def encode_query(self, text):
        return self._encode([text], self._manifest['query_prefix'])[0]
