#!/usr/bin/env python3
"""Simple evaluation wrapper for YOLOv8 models."""
from pathlib import Path
import argparse
from ultralytics import YOLO

ROOT = Path(__file__).resolve().parents[1]
DATA_YAML = ROOT / "dataset" / "processed" / "data.yaml"


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate a YOLO model")
    parser.add_argument("--model", type=str, default="models/best.pt")
    parser.add_argument("--data", type=str, default=str(DATA_YAML))
    args = parser.parse_args()

    model = YOLO(args.model)
    metrics = model.val(data=args.data)
    print(metrics)


if __name__ == "__main__":
    main()
