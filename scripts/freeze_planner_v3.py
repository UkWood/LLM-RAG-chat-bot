"""Pin a qualified V3 candidate before any blind payload parse/evaluation."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend/src'))
from saturn_ai.evaluation.planner_v3 import create_v3_freeze
p=argparse.ArgumentParser()
for name in ('dataset','calibration-report','model-dir','reranker-dir','freeze'):p.add_argument('--'+name,type=Path,required=True)
a=p.parse_args()
try:print(json.dumps(create_v3_freeze(a.dataset,a.calibration_report,a.model_dir,a.reranker_dir,a.freeze),indent=2,ensure_ascii=False))
except (ValueError,OSError,KeyError):p.exit(2,'V3 freeze rejected; qualified calibration and clean committed identities required.\n')
