import contextlib,io,json,unittest
from unittest.mock import patch
from saturn_ai.evaluation.__main__ import main

class CLITests(unittest.TestCase):
    def test_infeasible_calibration_is_exit_one_not_success(self):
        argv=['evaluate','--stage','v3-calibration','--mode','hybrid','--corpus','fixtures/evaluation',
              '--dataset','evaluation/datasets/planner-v3-calibration.json','--model-dir','test-model','--reranker-dir','test-pair','--require-feasibility']
        output=io.StringIO()
        with patch('sys.argv',argv),contextlib.redirect_stdout(output),contextlib.redirect_stderr(io.StringIO()),patch('saturn_ai.evaluation.planner_v3.run_v3_calibration',return_value=dict(feasible=False)):
            self.assertEqual(main(),1)
        self.assertFalse(json.loads(output.getvalue())['feasible'])
