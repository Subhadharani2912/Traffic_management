#!/usr/bin/env python3
"""Train a YOLOv8 model on prepared UA-DETRAC data."""
from pathlib import Path
import argparse

ROOT = Path(__file__).resolve().parents[1]
DATA_YAML = ROOT / "dataset" / "processed" / "data.yaml"
MODEL_DIR = ROOT / "models"
MODEL_DIR.mkdir(exist_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Train YOLO model")
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=8)
    parser.add_argument("--model", type=str, default="yolov8n.pt")
    parser.add_argument("--data", type=str, default=str(DATA_YAML))
    args = parser.parse_args()

    from ultralytics import YOLO

    if not Path(args.data).exists():
        raise FileNotFoundError(f"Dataset YAML not found: {args.data}")

    model = YOLO(args.model)
    results = model.train(
        data=args.data,
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        project=str(MODEL_DIR),
        name="training",
        exist_ok=True,
        pretrained=True,
    )
    print(results)


if __name__ == "__main__":
    main()
