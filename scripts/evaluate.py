#!/usr/bin/env python3
"""Evaluation wrapper for YOLOv8 models (UA-DETRAC and Emergency Vehicles)."""
from pathlib import Path
import argparse
from ultralytics import YOLO

ROOT = Path(__file__).resolve().parents[1]
DETRAC_DATA_YAML = ROOT / "dataset" / "processed" / "data.yaml"
EMERGENCY_DATA_YAML = ROOT / "dataset" / "emergency" / "data.yaml"


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate a YOLO model")
    parser.add_argument("--model", type=str, default=None)
    parser.add_argument("--data", type=str, default=None)
    parser.add_argument("--emergency", action="store_true", help="Evaluate dedicated emergency model")
    args = parser.parse_args()

    if args.emergency:
        model_path = args.model or "models/emergency_best.pt"
        data_path = args.data or str(EMERGENCY_DATA_YAML)
        print("[Evaluate] Evaluating EMERGENCY VEHICLE MODEL")
    else:
        model_path = args.model or "models/best.pt"
        data_path = args.data or str(DETRAC_DATA_YAML)
        print("[Evaluate] Evaluating PRIMARY VEHICLE MODEL")

    if not Path(model_path).exists():
        raise FileNotFoundError(f"Model file not found: {model_path}")
    if not Path(data_path).exists():
        raise FileNotFoundError(f"Dataset YAML not found: {data_path}")

    model = YOLO(model_path)
    metrics = model.val(data=data_path)
    print("\n[Evaluation Results]")
    print(metrics)


if __name__ == "__main__":
    main()
