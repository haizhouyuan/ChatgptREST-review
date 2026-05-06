#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from chatgptrest.evomap.knowledge.review_experiment import compare_review_outputs, load_review_json


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare a lane review output against a gold pack")
    parser.add_argument("--gold", required=True)
    parser.add_argument("--lane", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()

    result = compare_review_outputs(load_review_json(args.gold), load_review_json(args.lane))
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        print(out)
    else:
        print(text)


if __name__ == "__main__":
    main()

