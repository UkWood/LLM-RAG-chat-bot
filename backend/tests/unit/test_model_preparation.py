from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import numpy as np

from saturn_ai.retrieval.model_preparation import prepare_local_model, read_model_provenance


def profile(**changes):
    data=dict(schema_version=1,model_id='test-only/numeric-graph',revision='c'*40,
              source_url='https://huggingface.co/test-only/numeric-graph/tree/'+'c'*40,
              license_id='CC0-1.0',review_reference='unit-test authored graph; no semantic quality claim',
              purpose='runtime_contract',dimensions=2,max_length=128,query_prefix='',passage_prefix='',
              pad_id=0,output_name='last_hidden_state',pooling='mean')
    data.update(changes);return json.dumps(data).encode()


def inputs(root):
    root.mkdir()
    for name,data in [('model.onnx',b'placeholder'),('tokenizer.json',b'{}'),
                      ('MODEL_CARD.md',b'Authored numeric graph only.'),('LICENSE',b'CC0 synthetic fixture.')]:
        (root/name).write_bytes(data)
    return [root/name for name in ('model.onnx','tokenizer.json','MODEL_CARD.md','LICENSE')]


class NumericEncoder:
    def __init__(self,path):
        self.identity=dict(kind='local_onnx',**json.loads((path/'manifest.json').read_text()))
    def encode_documents(self,texts):return [[1.,0.] for _ in texts]
    def encode_query(self,text):return [1.,0.]


class ModelPreparationTests(unittest.TestCase):
    def test_staged_import_pins_all_artifacts_and_is_repeatable(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);files=inputs(root/'source')
            with patch('saturn_ai.retrieval.model_preparation.LocalONNXEncoder',NumericEncoder):
                first=prepare_local_model(profile(),*files,root/'first')
                reordered=json.dumps(dict(reversed(list(json.loads(profile()).items())))).encode()
                second=prepare_local_model(reordered,*files,root/'second')
            self.assertEqual(first,second)
            for name in ('manifest.json','provenance.json','smoke.json'):
                self.assertEqual((root/'first'/name).read_bytes(),(root/'second'/name).read_bytes())
            result=read_model_provenance(root/'first',require_semantic=False)
            self.assertEqual(result['profile']['purpose'],'runtime_contract')
            self.assertEqual(result['model_card_sha256'],sha256(files[2].read_bytes()).hexdigest())
            self.assertEqual(result['semantic_quality'],'not_measured')
            with self.assertRaises(ValueError):read_model_provenance(root/'first',require_semantic=True)

    def test_source_url_rejects_normalized_control_characters(self):
        from saturn_ai.retrieval.model_preparation import _profile
        for url in ['https://\nhuggingface.co/test-only/numeric-graph/tree/'+'c'*40,
                    'https://huggingface.co/test-only/numeric-graph/tree/'+'c'*20+'\t'+'c'*20]:
            with self.subTest(url=url), self.assertRaises(ValueError):
                _profile(profile(source_url=url))

    def test_invalid_profile_does_not_publish(self):
        for changes in [dict(revision='main'),dict(source_url='https://evil.invalid/repo'),
                        dict(source_url='https://\nhuggingface.co/test-only/numeric-graph/tree/'+'c'*40),
                        dict(source_url='https://user:pass@huggingface.co/a'),dict(source_url='http://huggingface.co/a'),
                        dict(source_url='https://huggingface.co/test-\nonly/numeric-graph/tree/'+'c'*40),
                        dict(source_url='https://huggingface.co/test-only/numeric-graph/tree/'+'d'*40),
                        dict(license_id='UNKNOWN'),dict(review_reference=''),dict(dimensions=True),
                        dict(purpose='production'),dict(extra=True)]:
            with tempfile.TemporaryDirectory() as temp:
                root=Path(temp);files=inputs(root/'source')
                with self.subTest(changes=changes):
                    with self.assertRaises(ValueError):prepare_local_model(profile(**changes),*files,root/'destination')
                    self.assertFalse((root/'destination').exists())

    def test_existing_destination_preserved_and_bad_smoke_cleans_staging(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);files=inputs(root/'source');dest=root/'destination';dest.mkdir();(dest/'keep').write_text('keep')
            with self.assertRaises((ValueError,FileExistsError)):prepare_local_model(profile(),*files,dest)
            self.assertEqual((dest/'keep').read_text(),'keep')
            with patch('saturn_ai.retrieval.model_preparation.LocalONNXEncoder',side_effect=ValueError('bad graph')):
                with self.assertRaises(ValueError):prepare_local_model(profile(),*files,root/'bad')
            self.assertFalse((root/'bad').exists())
            self.assertEqual({p.name for p in root.iterdir()},{'source','destination'})

    def test_concurrent_destination_is_not_replaced_at_publication(self):
        from saturn_ai.retrieval import model_preparation
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);files=inputs(root/'source');dest=root/'destination'
            publish=model_preparation._publish_new_directory
            def racing_publish(staging,target):
                target.mkdir();(target/'keep').write_text('concurrent owner data')
                return publish(staging,target)
            with patch.object(model_preparation,'LocalONNXEncoder',NumericEncoder), patch.object(model_preparation,'_publish_new_directory',new=racing_publish):
                with self.assertRaises(FileExistsError):prepare_local_model(profile(),*files,dest)
            self.assertEqual((dest/'keep').read_text(),'concurrent owner data')
            self.assertEqual({p.name for p in root.iterdir()},{'source','destination'})

    def test_leaf_symlink_and_empty_license_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);files=inputs(root/'source')
            link=root/'linked.onnx';link.symlink_to(files[0])
            with self.assertRaises((ValueError,OSError)):prepare_local_model(profile(),link,*files[1:],root/'one')
            files[3].write_bytes(b'')
            with self.assertRaises(ValueError):prepare_local_model(profile(),*files,root/'two')

    def test_bundle_provenance_tamper_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);files=inputs(root/'source');dest=root/'prepared'
            with patch('saturn_ai.retrieval.model_preparation.LocalONNXEncoder',NumericEncoder):
                prepare_local_model(profile(),*files,dest)
            original=(dest/'provenance.json').read_bytes()
            data=json.loads(original);data['profile']['purpose']='semantic_candidate';(dest/'provenance.json').write_text(json.dumps(data))
            with self.assertRaises(ValueError):read_model_provenance(dest,require_semantic=True)
            (dest/'provenance.json').write_bytes(original);(dest/'LICENSE').write_text('changed')
            with self.assertRaises(ValueError):read_model_provenance(dest,require_semantic=False)


HAS_ONNX=all(importlib.util.find_spec(name) is not None for name in ('onnx','onnxruntime','tokenizers'))


@unittest.skipUnless(HAS_ONNX,'requires optional ONNX profile')
class ActualPreparationTests(unittest.TestCase):
    def make_source(self,root,external=False):
        import unit.test_embeddings as fixtures
        root.mkdir();case=fixtures.ActualONNXContractTests('test_actual_runtime_accepts_embedded_numeric_graph')
        case.write_checkpoint(root,external=external)
        (root/'MODEL_CARD.md').write_text('Authored numeric graph, not a pretrained model.')
        (root/'LICENSE').write_text('CC0 synthetic fixture.')
        return [root/name for name in ('model.onnx','tokenizer.json','MODEL_CARD.md','LICENSE')]

    def test_actual_numeric_import_and_external_graph_cleanup(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);files=self.make_source(root/'source')
            result=prepare_local_model(profile(),*files,root/'prepared')
            self.assertEqual(result['inference_smoke'],'passed')
            self.assertFalse(result['eligible_for_candidate_benchmark'])
            bad=self.make_source(root/'external',external=True)
            with self.assertRaises(ValueError):prepare_local_model(profile(),*bad,root/'rejected')
            self.assertFalse((root/'rejected').exists())

    def test_runtime_contract_bundle_not_allowed_in_semantic_evaluation(self):
        from saturn_ai.evaluation.retrieval import run_retrieval_evaluation
        from unit.test_evaluation import CORPUS,DATASET
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);files=self.make_source(root/'source');dest=root/'prepared'
            prepare_local_model(profile(),*files,dest)
            with self.assertRaises(ValueError):run_retrieval_evaluation(CORPUS,DATASET,mode='hybrid',model_directory=dest)

    def test_complete_bundle_swap_during_evaluation_is_rejected(self):
        from saturn_ai.evaluation.retrieval import run_retrieval_evaluation
        from saturn_ai.retrieval.embeddings import LocalONNXEncoder
        from unit.test_evaluation import CORPUS, DATASET
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);files=self.make_source(root/'source')
            semantic=profile(purpose='semantic_candidate')
            prepare_local_model(semantic,*files,root/'active')
            files[2].write_text('Different reviewed card for identical graph')
            prepare_local_model(semantic,*files,root/'replacement')
            def swap(directory):
                directory.rename(root/'old')
                (root/'replacement').rename(directory)
                return LocalONNXEncoder(directory)
            with patch('saturn_ai.evaluation.retrieval.LocalONNXEncoder',side_effect=swap), patch(
                    'saturn_ai.evaluation.retrieval.QdrantIndex',side_effect=AssertionError('Changed bundle reached indexing')):
                with self.assertRaisesRegex(ValueError,'changed during loading'):
                    run_retrieval_evaluation(CORPUS,DATASET,mode='dense',model_directory=root/'active')
