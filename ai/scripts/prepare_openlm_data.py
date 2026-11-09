"""Prepare SFT conversations and final-assistant labels, without model weights."""
import argparse
import json
from pathlib import Path
import sys

AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT / "src"))
from evolv_openlm.runtime import DEFAULT_CACHE, load_settings
from evolv_openlm.sft_data import prepare, read_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=AI_ROOT / "data/sft/1.0.0")
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE)
    args = parser.parse_args()
    from transformers import AutoTokenizer
    config = load_settings()
    tokenizer = AutoTokenizer.from_pretrained(config["model_id"], revision=config["revision"],
        cache_dir=str(args.cache_dir), local_files_only=True, token=False, trust_remote_code=False)
    snapshot = args.cache_dir / ("models--" + config["model_id"].replace("/", "--")) / "snapshots" / config["revision"]
    files = [snapshot / "tokenizer.json", snapshot / "tokenizer_config.json"]
    report = prepare(AI_ROOT, args.output, tokenizer, files, read_json(AI_ROOT / "configs/openlm.data.v1.json"))
    print(json.dumps({k: report[k] for k in ["accepted", "excluded", "covered_intents", "covered_risks", "missing_intents", "missing_risks"]}, ensure_ascii=False))
    for split, stats in report["splits"].items():
        print(split, {k: stats[k] for k in ["conversations", "groups", "multiturn", "tokens", "target_tokens", "max_tokens"]})


if __name__ == "__main__":
    main()
