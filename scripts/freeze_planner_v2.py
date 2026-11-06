"""Create immutable pre-blind freeze metadata; never parses blind questions/labels."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend/src'))
from saturn_ai.evaluation.planner_v2 import create_freeze

parser=argparse.ArgumentParser()
for name in ('dataset','model-dir','reranker-dir','freeze'):parser.add_argument('--'+name,type=Path,required=True)
args=parser.parse_args()
try:print(json.dumps(create_freeze(args.dataset,args.model_dir,args.reranker_dir,args.freeze),indent=2))
except (ValueError,OSError):parser.exit(2,'Planner freeze rejected; clean committed identities required.\n')
