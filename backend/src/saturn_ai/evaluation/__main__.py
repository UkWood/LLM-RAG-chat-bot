"""Synthetic preflight or measured retrieval. Never claims unrun answer quality."""
import argparse
import json
from pathlib import Path
from .dataset import run_preflight


def main():
    parser=argparse.ArgumentParser(description='Synthetic preflight / measured local retrieval')
    parser.add_argument('--corpus',type=Path,required=True)
    parser.add_argument('--dataset',type=Path,required=True)
    parser.add_argument('--stage',choices=['preflight','retrieval','reranking','grounding','planner-calibration','planner-blind'],default='preflight')
    parser.add_argument('--mode',choices=['lexical','dense','hybrid'],default='lexical')
    parser.add_argument('--model-dir',type=Path)
    parser.add_argument('--reranker-dir',type=Path)
    parser.add_argument('--require-source-hit-target',action='store_true')
    parser.add_argument('--require-grounding-target',action='store_true')
    parser.add_argument('--freeze',type=Path)
    parser.add_argument('--planner-report',type=Path)
    parser.add_argument('--require-planner-target',action='store_true')
    args=parser.parse_args()
    try:
        if args.require_planner_target and args.stage!='planner-blind':raise ValueError('Planner target requires frozen blind comparison')
        if args.require_grounding_target and args.stage!='grounding':raise ValueError('Grounding target requires grounding stage')
        if args.stage in ('planner-calibration','planner-blind'):
            if args.mode!='hybrid' or args.model_dir is None or args.reranker_dir is None or args.require_source_hit_target or args.require_grounding_target:
                raise ValueError('Explicit hybrid bundles and comparison stage required')
            from .planner_v2 import run_calibration_comparison,run_blind_comparison
            if args.stage=='planner-blind':
                if args.freeze is None or args.planner_report is None:raise ValueError('Frozen first run/report required')
                report=run_blind_comparison(args.corpus,args.dataset,args.model_dir,args.reranker_dir,args.freeze,args.planner_report)
            else:
                report=run_calibration_comparison(args.corpus,args.dataset,args.model_dir,args.reranker_dir)
                if args.planner_report:args.planner_report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        elif args.stage=='preflight':
            if args.model_dir or args.reranker_dir or args.mode!='lexical' or args.require_source_hit_target:
                raise ValueError('Retrieval options require retrieval stage')
            report=run_preflight(args.corpus,args.dataset)
        elif args.stage=='grounding':
            if args.mode!='hybrid' or args.model_dir is None or args.reranker_dir is None or args.require_source_hit_target:
                raise ValueError('Grounding requires explicit hybrid bundles and its own quality gate')
            from .grounding import run_grounding_evaluation
            report=run_grounding_evaluation(args.corpus,args.dataset,args.model_dir,args.reranker_dir)
        elif args.stage=='reranking':
            if args.mode!='hybrid' or args.model_dir is None or args.reranker_dir is None:
                raise ValueError('Explicit hybrid embedding and reranker bundles required')
            from .reranking import run_reranking_evaluation
            report=run_reranking_evaluation(args.corpus,args.dataset,args.model_dir,args.reranker_dir)
        else:
            if args.reranker_dir is not None:raise ValueError('Reranker requires reranking stage')
            from .retrieval import run_retrieval_evaluation
            report=run_retrieval_evaluation(args.corpus,args.dataset,mode=args.mode,model_directory=args.model_dir)
    except (ValueError,OSError,RecursionError):
        parser.exit(2,'Synthetic evaluation rejected.\n')
    print(json.dumps(report,ensure_ascii=False,indent=2))
    if args.require_planner_target and not report['new_quality_target_met']:return 1
    if args.require_grounding_target and not report['grounding_target_met']:return 1
    return 1 if args.require_source_hit_target and not report['source_hit_target_met'] else 0


if __name__=='__main__':raise SystemExit(main())
