"""Ask the local submission a question using the unpacked participant kit."""
import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

root = Path(__file__).resolve().parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("question", nargs="?")
parser.add_argument("--as-of", metavar="YYYY-MM-DD")
parser.add_argument("--conflicts", action="store_true")
parser.add_argument("--kit", type=Path, default=root / "hackathon-knowledge-kit-participant")
args = parser.parse_args()
if not args.conflicts and not args.question:
    parser.error("Enter a question or use --conflicts.")
if not (args.kit / "harness/run_eval.py").is_file():
    parser.error("Pass --kit with the path to the extracted participant kit.")
sys.path[:0] = [str(root / "submission"), str(args.kit / "harness")]
from run_eval import load_snapshots
from solution import build

system = build()
for snapshot in load_snapshots(args.kit / "snapshots"):
    system.ingest(snapshot)
if args.conflicts:
    print(json.dumps([asdict(c) for c in system.conflicts()], indent=2, ensure_ascii=False))
else:
    print(json.dumps(asdict(system.answer(args.question, args.as_of)), indent=2, ensure_ascii=False))
