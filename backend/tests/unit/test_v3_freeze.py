"""First-attempt protocol on temporary schema bytes, never the actual blind set."""
import hashlib,json
from pathlib import Path
import tempfile,unittest
from unittest.mock import patch
from saturn_ai.evaluation.planner_v3 import create_v3_freeze,run_v3_blind
from saturn_ai.grounding.v3_config import load_v3_config

class FreezeTests(unittest.TestCase):
    def test_setup_failure_persists_consumed_invalid_outcome_and_cannot_refreeze(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);ds=root/'evaluation/datasets';ds.mkdir(parents=True)
            data=ds/'custom.json';data.write_bytes(b'not parsed before model setup');digest=hashlib.sha256(data.read_bytes()).hexdigest()
            for name in ('planner-v3-calibration.json','synthetic-v1.json'):(ds/name).write_text('{}')
            data.with_name('custom.manifest.json').write_text(json.dumps(dict(profile='planner_v3_blind',sha256=digest,snapshot_id='s',registry_revision='r',
                independent_review=dict(semantic_label_review='passed',deduplication=dict(status='passed')),baseline_capability_review=dict(final_independent_review='passed'))))
            model=root/'model';pair=root/'pair';model.mkdir();pair.mkdir()
            for d in (model,pair):(d/'manifest.json').write_text('{}')
            sha=hashlib.sha256(b'{}').hexdigest();cal=root/'cal.json'
            cal.write_text(json.dumps(dict(feasible=True,selected_replay_matches=True,runtime_sha256='r',calibration_sha256=sha,legacy_sha256=sha,
                embedding_manifest_sha256=sha,reranker_manifest_sha256=sha,selected_settings=load_v3_config()[0],snapshot_id='s',registry_revision='r')))
            def git(*args):return '' if args[0]=='status' else 'a'*40
            with patch('saturn_ai.evaluation.planner_v3._root',return_value=root),patch('saturn_ai.evaluation.planner_v3._runtime_sha',return_value='r'),patch('saturn_ai.evaluation.planner_v3._git',side_effect=git):
                freeze=root/'freeze.json';create_v3_freeze(data,cal,model,pair,freeze)
                original=freeze.read_text();drift=json.loads(original);drift['selected_settings']['score_min']=5.
                freeze.write_text(json.dumps(drift))
                with patch('saturn_ai.evaluation.planner_v3._context',side_effect=AssertionError('must reject before setup')):
                    with self.assertRaises(ValueError):run_v3_blind(root,data,model,pair,freeze,root/'drift-out.json')
                self.assertFalse((root/'evaluation/experiments'/f'{digest}.START.json').exists())
                freeze.write_text(original)

                with patch('saturn_ai.evaluation.planner_v3._context',side_effect=ValueError('setup failed')):
                    with self.assertRaises(ValueError):run_v3_blind(root,data,model,pair,freeze,root/'out.json')
                report=json.loads((root/'out.json').read_text())
                self.assertEqual(report['failure_phase'],'model_setup');self.assertFalse(report['experiment_valid']);self.assertEqual(report['unexecuted_cases'],40);self.assertEqual(report['cases'],[])
                self.assertTrue((root/'evaluation/experiments'/f'{digest}.START.json').exists())
                with self.assertRaisesRegex(ValueError,'consumed'):create_v3_freeze(data,cal,model,pair,root/'other-freeze.json')
