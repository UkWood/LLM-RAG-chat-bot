"""One offline verification command after installing backend/requirements.lock."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description='Project/tests/synthetic baseline verification; measured lexical baseline; neural model optional')
    parser.add_argument('--report', type=Path, help='Optional small preflight report, not a corpus/index export')
    parser.add_argument('--retrieval-report', type=Path, help='Optional measured lexical retrieval report')
    parser.add_argument('--require-source-hit-target', action='store_true', help='Fail if lexical source-hit@5 is below1.0')
    args = parser.parse_args()
    env = dict(os.environ, PYTHONPATH=str(ROOT/'backend/src'))
    for command in ([sys.executable, 'scripts/check_project.py'],
                    [sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-v'],
                    [sys.executable, '-m', 'unittest', 'discover', '-s', 'backend/tests', '-v']):
        result = subprocess.run(command, cwd=ROOT, env=env, check=False)
        if result.returncode:
            return result.returncode
    sys.path.insert(0, str(ROOT/'backend/src'))
    from saturn_ai.evaluation.dataset import run_preflight
    from saturn_ai.evaluation.retrieval import run_retrieval_evaluation
    try:
        report = run_preflight(ROOT/'fixtures/evaluation', ROOT/'evaluation/datasets/synthetic-v1.json')
        measured = run_retrieval_evaluation(ROOT/'fixtures/evaluation', ROOT/'evaluation/datasets/synthetic-v1.json')
    except (ValueError, OSError, RecursionError):
        print('Synthetic baseline preflight rejected.', file=sys.stderr)
        return 1
    if args.report:
        path = args.report if args.report.is_absolute() else ROOT/args.report
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    if args.retrieval_report:
        path = args.retrieval_report if args.retrieval_report.is_absolute() else ROOT/args.retrieval_report
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(measured, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({key: report[key] for key in ('report_kind', 'snapshot_id', 'dataset_revision',
                    'document_count', 'chunk_count', 'case_count', 'quality_evaluation')}, ensure_ascii=False))
    print(json.dumps(dict(report_kind=measured['report_kind'],mode=measured['mode'],
                         metrics=measured['metrics'],source_hit_target_met=measured['source_hit_target_met'],
                         quality_evaluation=measured['quality_evaluation']),ensure_ascii=False))
    return 1 if args.require_source_hit_target and not measured['source_hit_target_met'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
