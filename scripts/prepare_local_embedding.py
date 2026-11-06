"""Explicit local import only; obtaining public weights is a separate operator step."""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend/src'))


def main():
    parser=argparse.ArgumentParser(description='Prepare trusted local ONNX embedding bundle, no downloads')
    for name in ('profile','model','tokenizer','model-card','license','destination'):
        parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args()
    from saturn_ai.retrieval.model_preparation import prepare_local_model
    try:
        receipt=prepare_local_model(args.profile.read_bytes(),args.model,args.tokenizer,args.model_card,args.license,args.destination)
    except (ValueError,OSError,RuntimeError,RecursionError):
        parser.exit(2,'Local checkpoint preparation rejected; existing destination preserved.\n')
    print(json.dumps(receipt,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
