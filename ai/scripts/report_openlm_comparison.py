"""Render an already completed inference comparison and its case-by-case AI review."""
import argparse
from pathlib import Path
import sys

AI_ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(AI_ROOT/"src"))
from evolv_openlm.comparison_report import render

if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run",type=Path,default=AI_ROOT/"artifacts/openlm_evaluation/1.0.1")
    args=parser.parse_args()
    summary,decision=render(args.run)
    print(decision)
    print(args.run/"RESULTS.md")
