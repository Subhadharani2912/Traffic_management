#!/usr/bin/env python3
"""Prepare UA-DETRAC dataset into YOLO-compatible structure.

UA-DETRAC layout:
    DETRAC-Images/
        DETRAC-Images/
            MVI_20011/
                img00001.jpg
                img00002.jpg
                ...
    DETRAC-Train-Annotations-XML/
        DETRAC-Train-Annotations-XML/
            MVI_20011.xml
            ...

Each sequence XML has <frame num="N"> elements whose target boxes map to
img%05d.jpg in the corresponding sequence image folder.
"""
from __future__ import annotations

import argparse
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import cv2

# YOLO class ids used by the fine-tuned model (matches backend DETRAC_CLASS_MAP)
CLASS_MAP = {
    "car": 0,
    "van": 1,
    "bus": 2,
    "others": 3,
}

DEFAULT_DATASET_ROOT = Path(__file__).resolve().parents[1]
RAW_ROOT = DEFAULT_DATASET_ROOT / "dataset" / "raw"
PROCESSED_ROOT = DEFAULT_DATASET_ROOT / "dataset" / "processed"

# DETRAC images are 960x540; used as a fallback when reading fails
DEFAULT_IMG_W = 960
DEFAULT_IMG_H = 540


def find_dataset_dir(base: Path, folder_name: str) -> Path | None:
    """Locate a DETRAC folder whether it sits at base or one level deeper."""
    candidates = [base / folder_name, base / "DETRAC-Images" / folder_name, RAW_ROOT / folder_name]
    inner = [base / folder_name / folder_name]
    for candidate in candidates + inner:
        if candidate.exists() and candidate.is_dir():
            return candidate
    return None


def find_sequence_dirs(images_root: Path) -> List[Path]:
    """Return all sequence subfolders (each holds img%05d.jpg frames)."""
    for inner_name in ["DETRAC-Images", "."]:
        base = images_root if inner_name == "." else images_root / inner_name
        if not base.exists():
            continue
        seqs = [d for d in base.iterdir() if d.is_dir()]
        if seqs:
            return sorted(seqs)
    return []


def find_annotation_file(xml_root: Path, sequence_name: str) -> Path | None:
    """Locate {sequence_name}.xml allowing an inner folder of the same name."""
    candidates = [
        xml_root / f"{sequence_name}.xml",
        xml_root / xml_root.name / f"{sequence_name}.xml",
    ]
    # Glob fallback for nested / renamed layouts
    if not any(c.exists() for c in candidates):
        matches = list(xml_root.rglob(f"{sequence_name}.xml"))
        if matches:
            return matches[0]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def parse_sequence_annotations(xml_path: Path) -> Dict[int, List[Tuple[int, float, float, float, float]]]:
    """Parse a DETRAC sequence XML into {frame_num: [(class_id, x1, y1, x2, y2), ...]}."""
    tree = ET.parse(xml_path)
    root = tree.getroot()
    frames: Dict[int, List[Tuple[int, float, float, float, float]]] = {}

    for frame in root.findall("frame"):
        num = int(frame.attrib.get("num", -1))
        if num < 0:
            continue
        boxes = []
        for target in frame.findall("target_list/target"):
            box = target.find("box")
            if box is None:
                continue
            left = float(box.attrib.get("left", 0))
            top = float(box.attrib.get("top", 0))
            width = float(box.attrib.get("width", 0))
            height = float(box.attrib.get("height", 0))
            if width <= 0 or height <= 0:
                continue

            attr = target.find("attribute")
            vehicle_type = (attr.attrib.get("vehicle_type", "others") if attr is not None else "others")
            cls_id = CLASS_MAP.get(vehicle_type.strip().lower(), CLASS_MAP["others"])

            boxes.append((cls_id, left, top, left + width, top + height))
        frames[num] = boxes

    return frames


def frame_num_from_filename(image_path: Path) -> int:
    """img00042.jpg -> 42"""
    stem = image_path.stem
    digits = "".join(ch for ch in stem if ch.isdigit())
    return int(digits) if digits else -1


def convert_bbox_to_yolo(x1: float, y1: float, x2: float, y2: float, img_w: int, img_h: int) -> Tuple[float, float, float, float]:
    cx = ((x1 + x2) / 2.0) / img_w
    cy = ((y1 + y2) / 2.0) / img_h
    bw = (x2 - x1) / img_w
    bh = (y2 - y1) / img_h
    # Clamp to valid YOLO range
    cx = max(0.0, min(1.0, cx))
    cy = max(0.0, min(1.0, cy))
    bw = max(0.0, min(1.0, bw))
    bh = max(0.0, min(1.0, bh))
    return cx, cy, bw, bh


def image_size(image_path: Path) -> Tuple[int, int]:
    try:
        img = cv2.imread(str(image_path))
        if img is not None:
            h, w = img.shape[:2]
            return w, h
    except Exception:
        pass
    return DEFAULT_IMG_W, DEFAULT_IMG_H


def copy_and_prepare_dataset(images_root: Path, xml_root: Path, out_root: Path, split_ratios: Dict[str, float]) -> None:
    sequences = find_sequence_dirs(images_root)
    if not sequences:
        raise FileNotFoundError(f"No DETRAC sequence folders found under {images_root}")

    # Flatten all image paths with their (seq, frame) keys
    all_images: List[Tuple[Path, str, int]] = []
    for seq_dir in sequences:
        seq_name = seq_dir.name
        for img in sorted(seq_dir.glob("*.jpg")):
            all_images.append((img, seq_name, frame_num_from_filename(img)))
        for img in sorted(seq_dir.glob("*.png")):
            all_images.append((img, seq_name, frame_num_from_filename(img)))

    if not all_images:
        raise FileNotFoundError(f"No image files found in {images_root}")

    # Load annotation map once per sequence
    annotation_cache: Dict[str, Dict[int, List[Tuple[int, float, float, float, float]]]] = {}
    missing_xml: set = set()
    # Image size is constant within a sequence; read it only once
    sequence_sizes: Dict[str, Tuple[int, int]] = {}

    # Prepare output splits
    for split in ["train", "val", "test"]:
        (out_root / "images" / split).mkdir(parents=True, exist_ok=True)
        (out_root / "labels" / split).mkdir(parents=True, exist_ok=True)

    total = len(all_images)
    train_end = int(total * split_ratios["train"])
    val_end = train_end + int(total * split_ratios["val"])

    split_for_index = [0] * total
    for i in range(total):
        if i < train_end:
            split_for_index[i] = 0
        elif i < val_end:
            split_for_index[i] = 1
        else:
            split_for_index[i] = 2

    split_names = ["train", "val", "test"]
    copied = 0
    labeled = 0

    for i, (image_path, seq_name, frame_num) in enumerate(all_images):
        split = split_names[split_for_index[i]]
        # Prefix with sequence name to avoid collisions (every sequence has img00001.jpg)
        out_name = f"{seq_name}_{image_path.name}"
        target_image = out_root / "images" / split / out_name
        if not target_image.exists():
            shutil.copy2(image_path, target_image)
        copied += 1

        label_lines: List[str] = []

        if seq_name not in annotation_cache:
            annotation_cache[seq_name] = {}
            xml_file = find_annotation_file(xml_root, seq_name)
            if xml_file is not None:
                try:
                    annotation_cache[seq_name] = parse_sequence_annotations(xml_file)
                except Exception as exc:
                    print(f"[WARN] Failed to parse {xml_file}: {exc}")
            else:
                missing_xml.add(seq_name)

        frame_boxes = annotation_cache[seq_name].get(frame_num, [])
        if frame_boxes:
            if seq_name not in sequence_sizes:
                sequence_sizes[seq_name] = image_size(image_path)
            w_img, h_img = sequence_sizes[seq_name]
            label_lines = [
                "{} {:.6f} {:.6f} {:.6f} {:.6f}".format(
                    cls_id, *convert_bbox_to_yolo(x1, y1, x2, y2, w_img, h_img)
                )
                for cls_id, x1, y1, x2, y2 in frame_boxes
            ]
            labeled += 1

        label_target = out_root / "labels" / split / f"{seq_name}_{image_path.stem}.txt"
        label_target.write_text("\n".join(label_lines) + ("\n" if label_lines else ""), encoding="utf-8")

    data_yaml = out_root / "data.yaml"
    data_yaml.write_text(
        "train: dataset/processed/images/train\n"
        "val: dataset/processed/images/val\n"
        "test: dataset/processed/images/test\n\n"
        "nc: 4\n\n"
        "names: ['car', 'van', 'bus', 'others']\n",
        encoding="utf-8",
    )

    print(f"Prepared dataset under: {out_root}")
    print(f"Total images copied      : {copied}/{total}")
    print(f"Images with labels       : {labeled}")
    print(f"Sequences without XML    : {sorted(missing_xml) if missing_xml else 'none'}")
    for split in split_names:
        n = len(list((out_root / "images" / split).glob("*")))
        print(f"  {split:5s}: {n} images")


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare UA-DETRAC dataset into YOLO format")
    parser.add_argument("--images", type=str, default=str(RAW_ROOT / "DETRAC-Images"),
                        help="Folder containing DETRAC-Images (or sequence subfolders)")
    parser.add_argument("--annotations", type=str, default=str(RAW_ROOT / "DETRAC-Train-Annotations-XML"),
                        help="XML annotations folder (train)")
    parser.add_argument("--test-annotations", type=str, default=str(RAW_ROOT / "DETRAC-Test-Annotations-XML"),
                        help="XML annotations folder (test)")
    parser.add_argument("--output", type=str, default=str(PROCESSED_ROOT), help="Output processed dataset root")
    args = parser.parse_args()

    images_root = Path(args.images)
    train_xml_root = Path(args.annotations)
    out_root = Path(args.output)

    # Auto-detect dataset in workspace root when not in dataset/raw
    if not images_root.exists():
        auto_images = DEFAULT_DATASET_ROOT / "DETRAC-Images"
        if auto_images.exists():
            images_root = auto_images
    if not train_xml_root.exists():
        auto_xml = DEFAULT_DATASET_ROOT / "DETRAC-Train-Annotations-XML"
        if auto_xml.exists():
            train_xml_root = auto_xml

    if not images_root.exists():
        raise FileNotFoundError(f"Image dataset not found: {images_root}")
    if not train_xml_root.exists():
        raise FileNotFoundError(f"Train annotation dataset not found: {train_xml_root}")

    out_root.mkdir(parents=True, exist_ok=True)
    copy_and_prepare_dataset(images_root, train_xml_root, out_root, {"train": 0.7, "val": 0.2, "test": 0.1})


if __name__ == "__main__":
    main()