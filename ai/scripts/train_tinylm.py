"""Phase 7.03.4: train the local TinyLM, with validation and resumable checkpoints."""
import argparse
import json
from pathlib import Path
import sys

AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT / "src"))


def main():
    from evolv_tinylm.model import TinyLMConfig
    from evolv_tinylm.training import TrainingConfig, train

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=AI_ROOT / "artifacts/tinylm_data/1.0.0")
    parser.add_argument("--model-config", type=Path, default=AI_ROOT / "configs/tinylm.v1.json")
    parser.add_argument("--training-config", type=Path, default=AI_ROOT / "configs/tinylm.training.v1.json")
    parser.add_argument("--output", type=Path, default=AI_ROOT / "artifacts/tinylm_training/1.0.0")
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--stop-after-epoch", type=int, help="Stop at an epoch boundary; resume with the same config.")
    args = parser.parse_args()
    result = train(args.data, TinyLMConfig.load(args.model_config), TrainingConfig.load(args.training_config),
                   args.output, device=args.device, resume=args.resume, stop_after_epoch=args.stop_after_epoch)
    print(json.dumps(result, ensure_ascii=True, indent=2), flush=True)


if __name__ == "__main__":
    main()
