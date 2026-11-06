"""Authored dynamic numeric pair graphs: runtime contracts, never model quality."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
from saturn_ai.retrieval.reranker_model import (prepare_local_reranker, LocalONNXReranker,
    read_reranker_provenance, load_semantic_reranker)

HAS_ONNX=all(importlib.util.find_spec(n) for n in ('onnx','onnxruntime','tokenizers'))


def profile(**changes):
    result=dict(schema_version=1,kind='local_onnx_pair_scorer',model_id='test-only/pair-graph',revision='a'*40,
        source_url='https://huggingface.co/test-only/pair-graph/tree/'+'a'*40,license_id='CC0-1.0',
        review_reference='authored numeric test graph, no semantic claim',purpose='runtime_contract',
        max_length=512,pad_id=1,output_name='logits',activation='identity')
    result.update(changes);return json.dumps(result).encode()


def source(root,*,external=False,wrong_shape=False,nonfinite=False):
    import onnx
    from onnx import helper,TensorProto,numpy_helper
    from tokenizers import Tokenizer,models,pre_tokenizers,processors
    root.mkdir()
    tokenizer=Tokenizer(models.WordLevel({'[UNK]':0,'[PAD]':1,'[CLS]':2,'[SEP]':3,'one':4,'two':5,
                                         'synthetic':6,'query':7,'passage':8},unk_token='[UNK]'))
    tokenizer.pre_tokenizer=pre_tokenizers.Whitespace()
    tokenizer.post_processor=processors.TemplateProcessing(single='[CLS] $A [SEP]',
        pair='[CLS] $A [SEP] $B:1 [SEP]:1',special_tokens=[('[CLS]',2),('[SEP]',3)])
    (root/'tokenizer.json').write_text(tokenizer.to_str())
    inputs=[helper.make_tensor_value_info(n,TensorProto.INT64,['batch','tokens']) for n in ('input_ids','attention_mask')]
    axes=numpy_helper.from_array(np.array([1],dtype=np.int64),name='axes')
    bias=numpy_helper.from_array(np.array([float("nan") if nonfinite else 0.0],dtype=np.float32),name='bias')
    if external:
        bias=TensorProto(name='bias',data_type=TensorProto.FLOAT,dims=[1],data_location=TensorProto.EXTERNAL)
        bias.external_data.add(key='location',value='sidecar.bin')
    nodes=[helper.make_node('Cast',['input_ids'],['ids'],to=TensorProto.FLOAT),
           helper.make_node('Cast',['attention_mask'],['mask'],to=TensorProto.FLOAT),
           helper.make_node('Mul',['ids','mask'],['masked']),
           helper.make_node('ReduceSum',['masked','axes'],['total'],keepdims=0 if wrong_shape else 1),
           helper.make_node('Add',['total','bias'],['logits'])]
    out=helper.make_tensor_value_info('logits',TensorProto.FLOAT,['batch'] if wrong_shape else ['batch',1])
    model=helper.make_model(helper.make_graph(nodes,'numeric-pair-contract',inputs,[out],[axes,bias]),
                            opset_imports=[helper.make_operatorsetid('',13)],ir_version=8)
    (root/'model.onnx').write_bytes(model.SerializeToString())
    (root/'MODEL_CARD.md').write_text('Authored numeric pair graph, not language relevance.')
    (root/'LICENSE').write_text('CC0 authored test fixture')
    return [root/n for n in ('model.onnx','tokenizer.json','MODEL_CARD.md','LICENSE')]


class ProfileTests(unittest.TestCase):
    def test_invalid_profiles_rejected_before_files_read(self):
        for changes in [dict(max_length=True),dict(max_length=513),dict(activation='sigmoid'),dict(purpose='production'),
            dict(source_url='https://\nhuggingface.co/test-only/pair-graph/tree/'+'a'*40),dict(revision='main'),dict(extra=1)]:
            with self.subTest(changes=changes),self.assertRaises(ValueError):
                prepare_local_reranker(profile(**changes),'missing','missing','missing','missing','missing-destination')


@unittest.skipUnless(HAS_ONNX,'requires locked optional ONNX profile')
class PairRuntimeTests(unittest.TestCase):
    def prepare(self,root,**kwargs):
        files=source(root/'source',**kwargs);dest=root/'bundle'
        receipt=prepare_local_reranker(profile(),*files,dest)
        return files,dest,receipt

    def test_actual_dynamic_pair_batches_padding_truncation_and_repeatability(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);files,dest,first=self.prepare(root)
            second=prepare_local_reranker(profile(),*files,root/'second')
            self.assertEqual(first,second)
            scorer=LocalONNXReranker(dest)
            self.assertEqual(scorer.score_pairs('one',['two']),[17.0])
            result=scorer.score_pairs('one',['two','one two']*5)
            self.assertEqual(result,[17.0,21.0]*5)
            self.assertEqual(scorer.score_pairs('one',['two '*1000]),[2552.0])
            self.assertEqual(scorer.score_pairs('one',[]),[])
            with self.assertRaises(ValueError):load_semantic_reranker(dest)
            self.assertEqual(read_reranker_provenance(dest,require_semantic=False)['profile']['purpose'],'runtime_contract')

    def test_wrong_shape_external_data_and_cleanup(self):
        for kwargs in [dict(external=True),dict(wrong_shape=True),dict(nonfinite=True)]:
            with tempfile.TemporaryDirectory() as temp:
                root=Path(temp);files=source(root/'source',**kwargs)
                with self.assertRaises(ValueError):prepare_local_reranker(profile(),*files,root/'bundle')
                self.assertEqual({p.name for p in root.iterdir()},{'source'})

    def test_existing_concurrent_destination_symlink_and_drift(self):
        from saturn_ai.retrieval import reranker_model
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);files,dest,_=self.prepare(root)
            with self.assertRaises(FileExistsError):prepare_local_reranker(profile(),*files,dest)
            link=root/'link';link.symlink_to(files[0])
            with self.assertRaises(ValueError):prepare_local_reranker(profile(),link,*files[1:],root/'linked')
            publish=reranker_model._publish_new_directory
            def race(stage,target):target.mkdir();return publish(stage,target)
            with patch.object(reranker_model,'_publish_new_directory',side_effect=race):
                with self.assertRaises(FileExistsError):prepare_local_reranker(profile(),*files,root/'raced')
            self.assertTrue((root/'raced').is_dir())
            self.assertFalse(list(root.glob('.reranker-staging-*')))
            (dest/'tokenizer.json').write_text('{}')
            with self.assertRaises(ValueError):LocalONNXReranker(dest)

    def test_complete_bundle_swap_rejected_by_semantic_loader(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);files=source(root/'source');raw=profile(purpose='semantic_candidate')
            prepare_local_reranker(raw,*files,root/'active');files[2].write_text('other reviewed card')
            prepare_local_reranker(raw,*files,root/'other')
            original=LocalONNXReranker
            def swap(directory):
                directory.rename(root/'old');(root/'other').rename(directory);return original(directory)
            with patch('saturn_ai.retrieval.reranker_model.LocalONNXReranker',side_effect=swap):
                with self.assertRaisesRegex(ValueError,'changed during loading'):load_semantic_reranker(root/'active')

    def test_runtime_consumes_same_verified_bytes_if_files_change_at_load(self):
        from saturn_ai.retrieval import reranker_model
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);_,dest,_=self.prepare(root)
            original=reranker_model._load_runtime
            def swap(model_bytes,tokenizer_bytes,manifest):
                (dest/'model.onnx').write_bytes(b'changed after hashing')
                return original(model_bytes,tokenizer_bytes,manifest)
            with patch.object(reranker_model,'_load_runtime',side_effect=swap):
                scorer=LocalONNXReranker(dest)
            self.assertEqual(scorer.score_pairs('one',['two']),[17.0])
            with self.assertRaises(ValueError):read_reranker_provenance(dest,require_semantic=False)
