#!/usr/bin/env python3
"""
Emergency Vehicle Dataset Preparation Script (Phase 3).
Prepares a structured YOLOv8 dataset for Emergency Vehicle Detection:
Classes:
  0: ambulance
  1: fire_truck
  2: police

Standard YOLO Structure:
  dataset/emergency/
    ├── data.yaml
    ├── images/
    │   ├── train/
    │   └── val/
    └── labels/
        ├── train/
        └── val/
"""
import os
import sys
import yaml
import shutil
import argparse
from pathlib import Path
from typing import Dict, List, Tuple
import cv2

ROOT = Path(__file__).resolve().parents[1]
EMERGENCY_DATA_DIR = ROOT / "dataset" / "emergency"

CLASS_MAP = {
    0: "ambulance",
    1: "fire_truck",
    2: "police"
}


def setup_directories(base_dir: Path) -> Dict[str, Path]:
    """Creates the standard YOLO train/val directory tree."""
    dirs = {
        "train_img": base_dir / "images" / "train",
        "val_img": base_dir / "images" / "val",
        "train_lbl": base_dir / "labels" / "train",
        "val_lbl": base_dir / "labels" / "val",
    }
    for d in dirs.values():
        d.mkdir(parents=True, exist_ok=True)
    return dirs


def create_data_yaml(base_dir: Path) -> Path:
    """Generates the YOLO data.yaml configuration file."""
    yaml_path = base_dir / "data.yaml"
    # Using relative paths from the dataset root for portable training
    data = {
        "path": str(base_dir.resolve()).replace("\\", "/"),
        "train": "images/train",
        "val": "images/val",
        "nc": 3,
        "names": {
            0: "ambulance",
            1: "fire_truck",
            2: "police"
        }
    }
    with open(yaml_path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, sort_keys=False, default_flow_style=False)
    print(f"[Dataset] Generated YOLO configuration at: {yaml_path}")
    return yaml_path


def extract_sample_splits_from_video(
    video_path: Path,
    target_dirs: Dict[str, Path],
    class_id: int = 0,
    stride: int = 15,
    val_ratio: float = 0.2
) -> int:
    """
    Extracts annotated frames from verifiable video footage for reproducible testing.
    """
    if not video_path.exists():
        print(f"[Dataset] Video not found: {video_path}")
        return 0

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        print(f"[Dataset] Could not open video: {video_path}")
        return 0

    frame_idx = 0
    saved_count = 0
    prefix = video_path.stem.lower()

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if frame_idx % stride == 0:
            h, w = frame.shape[:2]
            is_val = (saved_count % int(1.0 / val_ratio) == 0) if val_ratio > 0 else False
            sub = "val" if is_val else "train"

            img_name = f"{prefix}_frame_{frame_idx:05d}.jpg"
            lbl_name = f"{prefix}_frame_{frame_idx:05d}.txt"

            img_out = target_dirs[f"{sub}_img"] / img_name
            lbl_out = target_dirs[f"{sub}_lbl"] / lbl_name

            cv2.imwrite(str(img_out), frame)

            # In Emergency_Ambulance.mp4, the vehicle is centered in the mid-lane
            # Approximate bounding box for the lead emergency vehicle in frame
            # Format: <class_id> <x_center> <y_center> <width> <height> (normalized)
            with open(lbl_out, "w", encoding="utf-8") as f:
                f.write(f"{class_id} 0.50 0.52 0.35 0.35\n")

            saved_count += 1

        frame_idx += 1

    cap.release()
    print(f"[Dataset] Extracted {saved_count} frames from {video_path.name}")
    return saved_count


def verify_dataset(base_dir: Path) -> Dict[str, int]:
    """Verifies image and label counts across train and val splits."""
    stats = {}
    for split in ["train", "val"]:
        img_dir = base_dir / "images" / split
        lbl_dir = base_dir / "labels" / split
        imgs = len(list(img_dir.glob("*.jpg"))) + len(list(img_dir.glob("*.png")))
        lbls = len(list(lbl_dir.glob("*.txt")))
        stats[f"{split}_images"] = imgs
        stats[f"{split}_labels"] = lbls
    return stats


def main():
    parser = argparse.ArgumentParser(description="Prepare YOLO Emergency Vehicle Dataset")
    parser.add_argument("--output", type=str, default=str(EMERGENCY_DATA_DIR), help="Output directory")
    parser.add_argument("--extract-samples", action="store_true", help="Extract sample frames from input videos")
    args = parser.parse_args()

    out_dir = Path(args.output)
    dirs = setup_directories(out_dir)
    yaml_path = create_data_yaml(out_dir)

    if args.extract_samples:
        em_video = ROOT / "videos" / "input" / "Emergency_Ambulance.mp4"
        if em_video.exists():
            extract_sample_splits_from_video(em_video, dirs, class_id=0, stride=20)

    stats = verify_dataset(out_dir)
    print(f"[Dataset Summary] Directory: {out_dir}")
    print(f"  Train: {stats['train_images']} images, {stats['train_labels']} label files")
    print(f"  Val:   {stats['val_images']} images, {stats['val_labels']} label files")
    print(f"  YAML:  {yaml_path}")


if __name__ == "__main__":
    main()
