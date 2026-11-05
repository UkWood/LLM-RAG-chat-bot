from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import numpy as np

from saturn_ai.retrieval.embeddings import LocalONNXEncoder, pool_embeddings


class EmbeddingTests(unittest.TestCase):
    def test_masked_mean_pooling_ignores_padding(self):
        hidden = np.array([[[1, 0], [0, 1], [999, 999]]], dtype=np.float32)
        result = pool_embeddings(hidden, np.array([[1, 1, 0]]), dimensions=2)
        self.assertTrue(np.allclose(result, [[0.70710678, 0.70710678]]))
        for bad in [np.array([[1,2,3]]), np.array([[[float('nan'),0]]]), np.array([[[0,0]]])]:
            with self.subTest(shape=bad.shape):
                with self.assertRaises(ValueError):
                    pool_embeddings(bad, np.array([[1]]), dimensions=2)

    def test_model_hash_checked_before_runtime_load(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root/'model.onnx').write_bytes(b'not-a-model')
            (root/'tokenizer.json').write_text('{}')
            manifest = dict(schema_version=1, model_id='owner-local-model', revision='pinned-revision',
                            dimensions=2, max_length=128, query_prefix='query: ', passage_prefix='passage: ',
                            pad_id=0, output_name='last_hidden_state', pooling='mean',
                            model_sha256='0'*64, tokenizer_sha256=sha256(b'{}').hexdigest())
            (root/'manifest.json').write_text(json.dumps(manifest))
            with patch('saturn_ai.retrieval.embeddings._load_runtime') as loader:
                with self.assertRaises(ValueError):
                    LocalONNXEncoder(root)
                loader.assert_not_called()

    def test_local_only_adapter_prefix_batch_and_output_contract(self):
        class Encoded:
            ids = [1,2]
            attention_mask = [1,1]
            type_ids = [0,0]
        class Tokenizer:
            def __init__(self): self.received=[]
            def encode_batch(self, texts): self.received.extend(texts);return [Encoded() for _ in texts]
        class Input:
            def __init__(self,name):self.name=name;self.type='tensor(int64)'
        class Session:
            def get_inputs(self):return [Input('input_ids'),Input('attention_mask')]
            def run(self, names, inputs):
                return [np.ones((len(inputs['input_ids']),2,2),dtype=np.float32)]
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'model.onnx').write_bytes(b'test-runtime-placeholder');(root/'tokenizer.json').write_bytes(b'{}')
            manifest=dict(schema_version=1,model_id='test-adapter-contract',revision='test-only',dimensions=2,
                          max_length=128,query_prefix='query: ',passage_prefix='passage: ',pad_id=0,
                          output_name='last_hidden_state',pooling='mean',model_sha256=sha256((root/'model.onnx').read_bytes()).hexdigest(),
                          tokenizer_sha256=sha256(b'{}').hexdigest())
            (root/'manifest.json').write_text(json.dumps(manifest))
            tokenizer=Tokenizer()
            with patch('saturn_ai.retrieval.embeddings._load_runtime',return_value=(tokenizer,Session())):
                encoder=LocalONNXEncoder(root)
                self.assertEqual(len(encoder.encode_documents(['a','b'])),2)
                self.assertEqual(len(encoder.encode_query('q')),2)
                self.assertEqual(tokenizer.received,['passage: a','passage: b','query: q'])
                self.assertEqual(encoder.identity['kind'],'local_onnx')
