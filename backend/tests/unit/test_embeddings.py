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

# Optional CI job installs the runtime profile; no checkpoint/model downloads.
import importlib.util
HAS_ONNX_RUNTIME = all(importlib.util.find_spec(name) is not None for name in ('onnx','onnxruntime','tokenizers'))


@unittest.skipUnless(HAS_ONNX_RUNTIME, 'requires hash-locked optional ONNX runtime profile')
class ActualONNXContractTests(unittest.TestCase):
    def write_checkpoint(self, root, *, external=False, absolute=False):
        import onnx
        from onnx import helper,TensorProto,numpy_helper
        from tokenizers import Tokenizer,models,pre_tokenizers
        tokenizer=Tokenizer(models.WordLevel({'[PAD]':0,'[UNK]':1,'one':2,'two':3},unk_token='[UNK]'))
        tokenizer.pre_tokenizer=pre_tokenizers.Whitespace()
        (root/'tokenizer.json').write_text(tokenizer.to_str())
        values=np.array([[[1.,0.],[1.,0.]]],dtype=np.float32)
        if external:
            (root/'weights.bin').write_bytes(values.tobytes())
            tensor=TensorProto(name='weights',data_type=TensorProto.FLOAT,dims=[1,2,2],data_location=TensorProto.EXTERNAL)
            tensor.external_data.add(key='location',value=str(root/'weights.bin') if absolute else 'weights.bin')
            tensor.external_data.add(key='length',value='16')
        else:
            tensor=numpy_helper.from_array(values,name='weights')
        inputs=[helper.make_tensor_value_info(name,TensorProto.INT64,[1,2]) for name in ('input_ids','attention_mask')]
        output=helper.make_tensor_value_info('last_hidden_state',TensorProto.FLOAT,[1,2,2])
        graph=helper.make_graph([helper.make_node('Identity',['weights'],['last_hidden_state'])],
                                'synthetic-runtime-contract',inputs,[output],[tensor])
        model=helper.make_model(graph,opset_imports=[helper.make_operatorsetid('',13)],ir_version=8)
        (root/'model.onnx').write_bytes(model.SerializeToString())
        manifest=dict(schema_version=1,model_id='synthetic-numeric-graph-not-embedding-model',revision='test-only',
                      dimensions=2,max_length=128,query_prefix='',passage_prefix='',pad_id=0,
                      output_name='last_hidden_state',pooling='mean',
                      model_sha256=sha256((root/'model.onnx').read_bytes()).hexdigest(),
                      tokenizer_sha256=sha256((root/'tokenizer.json').read_bytes()).hexdigest())
        (root/'manifest.json').write_text(json.dumps(manifest))

    def test_external_sidecar_graph_rejected_even_when_manifest_hashes_match(self):
        for absolute in (False,True):
            with tempfile.TemporaryDirectory() as temp:
                root=Path(temp);self.write_checkpoint(root,external=True,absolute=absolute)
                with self.subTest(absolute=absolute):
                    with self.assertRaises(ValueError):LocalONNXEncoder(root)

    def test_actual_runtime_accepts_embedded_numeric_graph(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);self.write_checkpoint(root)
            encoder=LocalONNXEncoder(root)
            self.assertTrue(np.allclose(encoder.encode_query('one two'),[1,0]))

    def test_runtime_uses_verified_bytes_if_files_change_after_hashing(self):
        from saturn_ai.retrieval import embeddings
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);self.write_checkpoint(root)
            original=embeddings._load_runtime
            def swapping_files(*args):
                (root/'model.onnx').write_bytes(b'replaced-after-verification')
                (root/'tokenizer.json').write_text('{}')
                return original(*args)
            with patch.object(embeddings,'_load_runtime',new=swapping_files):
                encoder=LocalONNXEncoder(root)
                self.assertTrue(np.allclose(encoder.encode_query('one two'),[1,0]))
