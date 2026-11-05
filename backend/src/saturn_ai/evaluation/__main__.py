"""Synthetic preflight or measured retrieval. Never claims unrun answer quality."""
import argparse
import json
from pathlib import Path
from .dataset import run_preflight


def main():
    parser=argparse.ArgumentParser(description='Synthetic preflight / measured local retrieval')
    parser.add_argument('--corpus',type=Path,required=True)
    parser.add_argument('--dataset',type=Path,required=True)
    parser.add_argument('--stage',choices=['preflight','retrieval'],default='preflight')
    parser.add_argument('--mode',choices=['lexical','dense','hybrid'],default='lexical')
    parser.add_argument('--model-dir',type=Path)
    parser.add_argument('--require-source-hit-target',action='store_true')
    args=parser.parse_args()
    try:
        if args.stage=='preflight':
            if args.model_dir or args.mode!='lexical' or args.require_source_hit_target:
                raise ValueError('Retrieval options require retrieval stage')
            report=run_preflight(args.corpus,args.dataset)
        else:
            from .retrieval import run_retrieval_evaluation
            report=run_retrieval_evaluation(args.corpus,args.dataset,mode=args.mode,model_directory=args.model_dir)
    except (ValueError,OSError,RecursionError):
        parser.exit(2,'Synthetic evaluation rejected.\n')
    print(json.dumps(report,ensure_ascii=False,indent=2))
    return 1 if args.require_source_hit_target and not report['source_hit_target_met'] else 0


if __name__=='__main__':raise SystemExit(main())
