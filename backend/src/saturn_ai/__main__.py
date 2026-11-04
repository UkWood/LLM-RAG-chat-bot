"""Run: PYTHONPATH=backend/src python3 -m saturn_ai --corpus fixtures/synthetic QUESTION"""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
from .application import Consultant
from .knowledge import load_snapshot
from .providers import FakeLLMProvider


def main():
    parser = argparse.ArgumentParser(description='Synthetic-only offline RAG (FakeLLMProvider)')
    parser.add_argument('--corpus', type=Path, required=True)
    parser.add_argument('question')
    args = parser.parse_args()
    try:
        snapshot = load_snapshot(args.corpus)
    except (ValueError, OSError):
        parser.exit(2, 'Invalid or unavailable synthetic corpus.\n')
    result = Consultant(snapshot, FakeLLMProvider()).answer(args.question)
    print(json.dumps(asdict(result), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
