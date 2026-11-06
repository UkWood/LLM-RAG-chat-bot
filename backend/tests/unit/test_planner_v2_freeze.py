"""Freeze protocol tests on temporary synthetic bytes, never the blinded payload."""
import hashlib,json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from saturn_ai.evaluation.planner_v2 import create_freeze,run_blind_comparison


class FreezeProtocolTests(unittest.TestCase):
    def test_dataset_is_consumed_even_if_model_setup_fails_and_new_freeze_path_is_chosen(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'config').mkdir();(root/'config/planner-v2.json').write_text('{}')
            projection=root/'backend/src/saturn_ai/grounding/projections.py';projection.parent.mkdir(parents=True);projection.write_text('test')
            dataset=root/'custom.json';dataset.write_bytes(b'not parsed in this setup-failure test')
            digest=hashlib.sha256(dataset.read_bytes()).hexdigest()
            dataset.with_name('custom.manifest.json').write_text(json.dumps(dict(dataset_sha256=digest,snapshot_id='test-only')))
            model=root/'model';reranker=root/'reranker';model.mkdir();reranker.mkdir()
            for p in (model,reranker):(p/'manifest.json').write_text('{}')
            def git(*args):return '' if args[0]=='status' else 'a'*40
            with patch('saturn_ai.evaluation.planner_v2._git_root',return_value=root),patch('saturn_ai.evaluation.planner_v2._git',side_effect=git):
                freeze=root/'freeze.json';create_freeze(dataset,model,reranker,freeze)
                projection.write_text('mutated outside Git-status fixture')
                with self.assertRaisesRegex(ValueError,'changed'):
                    run_blind_comparison(root,dataset,model,reranker,freeze,root/'report.json')
                self.assertFalse((root/'evaluation/experiments'/f'{digest}.START.json').exists())
                projection.write_text('test')
                with patch('saturn_ai.evaluation.planner_v2._context',side_effect=ValueError('model setup failed')):
                    with self.assertRaises(ValueError):run_blind_comparison(root,dataset,model,reranker,freeze,root/'report.json')
                failure=json.loads((root/'report.json').read_text())
                self.assertFalse(failure['experiment_valid'])
                self.assertEqual(failure['unexecuted_cases'],40)
                self.assertEqual(failure['cases'],[])
                self.assertTrue((root/'evaluation/experiments'/f'{digest}.START.json').exists())
                with self.assertRaisesRegex(ValueError,'consumed'):create_freeze(dataset,model,reranker,root/'other-freeze.json')
