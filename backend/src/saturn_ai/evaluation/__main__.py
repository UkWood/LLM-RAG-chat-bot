"""Print reproducible label preflight; no retrieval/LLM scoring is performed."""
import argparse
import json
from pathlib import Path
from .dataset import run_preflight


def main():
    parser = argparse.ArgumentParser(description='Synthetic snapshot/dataset preflight (quality not measured)')
    parser.add_argument('--corpus', type=Path, required=True)
    parser.add_argument('--dataset', type=Path, required=True)
    args = parser.parse_args()
    try:
        report = run_preflight(args.corpus, args.dataset)
    except (ValueError, OSError, RecursionError):
        parser.exit(2, 'Synthetic baseline preflight rejected.\n')
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
