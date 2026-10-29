#!/usr/bin/env python3
"""
Train a YOLOv8 model on prepared traffic data (UA-DETRAC or Emergency Vehicles).
Supports:
  --emergency: Trains the dedicated emergency vehicle detector on dataset/emergency/data.yaml
               and saves the resulting weights to models/emergency_best.pt
"""
from pathlib import Path
import argparse
import shutil

ROOT = Path(__file__).resolve().parents[1]
DETRAC_DATA_YAML = ROOT / "dataset" / "processed" / "data.yaml"
EMERGENCY_COMPACT_YAML = ROOT / "dataset" / "emergency_compact" / "data.yaml"
EMERGENCY_INDIAN_YAML = ROOT / "dataset" / "emergency_indian" / "data.yaml"
EMERGENCY_DATA_YAML = ROOT / "dataset" / "emergency" / "data.yaml"
MODEL_DIR = ROOT / "models"
MODEL_DIR.mkdir(exist_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Train YOLO model")
    parser.add_argument("--epochs", type=int, default=10, help="Number of training epochs")
    parser.add_argument("--imgsz", type=int, default=640, help="Image size")
    parser.add_argument("--batch", type=int, default=8, help="Batch size")
    parser.add_argument("--model", type=str, default="yolov8n.pt", help="Base model weights")
    parser.add_argument("--data", type=str, default=None, help="Custom data.yaml path")
    parser.add_argument("--emergency", action="store_true", help="Train dedicated emergency vehicle model")
    parser.add_argument("--fraction", type=float, default=1.0, help="Fraction of dataset images to use (CPU-friendly)")
    parser.add_argument("--device", type=str, default="cpu", help="Training device, e.g. cpu or 0")
    parser.add_argument("--name", type=str, default=None, help="Ultralytics run folder name")
    parser.add_argument("--freeze", type=int, default=0, help="Freeze first N layers (faster / cooler CPU training)")
    parser.add_argument("--patience", type=int, default=100, help="Early-stop patience")
    parser.add_argument("--threads", type=int, default=4, help="CPU threads (lower = less heat)")
    args = parser.parse_args()

    import os
    os.environ["OMP_NUM_THREADS"] = str(args.threads)
    os.environ["MKL_NUM_THREADS"] = str(args.threads)
    import torch
    torch.set_num_threads(args.threads)
    from ultralytics import YOLO

    # Determine dataset configuration and target model destination
    if args.emergency:
        if args.data:
            data_path = Path(args.data)
        elif EMERGENCY_COMPACT_YAML.exists():
            data_path = EMERGENCY_COMPACT_YAML
        elif EMERGENCY_INDIAN_YAML.exists():
            data_path = EMERGENCY_INDIAN_YAML
        else:
            data_path = EMERGENCY_DATA_YAML
        run_name = args.name or "emergency_training"
        target_best = MODEL_DIR / "emergency_best.pt"
        print("[Train] Mode: EMERGENCY VEHICLE MODEL TRAINING")
    else:
        data_path = Path(args.data) if args.data else DETRAC_DATA_YAML
        run_name = args.name or "traffic_training"
        target_best = MODEL_DIR / "best.pt"
        print("[Train] Mode: PRIMARY TRAFFIC VEHICLE MODEL TRAINING")

    if not data_path.exists():
        raise FileNotFoundError(f"Dataset YAML not found at: {data_path}. Please run dataset preparation first.")

    print(f"[Train] Using dataset configuration: {data_path}")
    print(
        f"[Train] Base weights: {args.model} | Epochs: {args.epochs} | Imgsz: {args.imgsz} | "
        f"Batch: {args.batch} | Freeze: {args.freeze} | Threads: {args.threads}"
    )

    model = YOLO(args.model)
    results = model.train(
        data=str(data_path),
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        project=str(MODEL_DIR / "runs"),
        name=run_name,
        exist_ok=True,
        pretrained=True,
        verbose=True,
        fraction=args.fraction,
        device=args.device,
        workers=0,
        freeze=args.freeze if args.freeze > 0 else None,
        patience=args.patience,
    )
    print(f"[Train] Training completed: {results}")

    # Copy best weights to the expected models destination
    saved_best = MODEL_DIR / "runs" / run_name / "weights" / "best.pt"
    if saved_best.exists():
        shutil.copy(saved_best, target_best)
        print(f"[Train] Successfully saved best weights to: {target_best} ({saved_best.stat().st_size} bytes)")
    else:
        print(f"[Train] Notice: {saved_best} not found, checking fallback weights.")


if __name__ == "__main__":
    main()

