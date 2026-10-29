#!/usr/bin/env python3
"""Remap the 24-class Indian emergency Roboflow export to 3 YOLO classes.

Keeps real vehicles only (not lamps/text/symbols) and builds a compact CPU-sized
subset so training can finish on this machine.
"""
from __future__ import annotations

import random
import shutil
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "dataset" / "emergency_indian"
DST = ROOT / "dataset" / "emergency_compact"

# Original 24-class ids from data.yaml
AMBULANCE_IDS = {2, 3, 4}  # ambulance, ambulance_108, ambulance_SOL
FIRE_IDS = {11, 12}  # fire_truck, fireladder
POLICE_IDS = {17}  # police
REMAP = {}
REMAP.update({i: 0 for i in AMBULANCE_IDS})
REMAP.update({i: 1 for i in FIRE_IDS})
REMAP.update({i: 2 for i in POLICE_IDS})

TRAIN_POS_CAP = 1800
TRAIN_NEG_CAP = 250
VAL_POS_CAP = 280
VAL_NEG_CAP = 40


def remap_label(src: Path) -> list[str]:
    out = []
    if not src.exists():
        return out
    for line in src.read_text(encoding="utf-8", errors="ignore").splitlines():
        parts = line.strip().split()
        if len(parts) < 5:
            continue
        try:
            cid = int(float(parts[0]))
        except ValueError:
            continue
        if cid not in REMAP:
            continue
        out.append(" ".join([str(REMAP[cid]), *parts[1:]]))
    return out


def collect(split: str) -> tuple[list[Path], list[Path]]:
    img_dir = SRC / split / "images"
    lbl_dir = SRC / split / "labels"
    positives: list[Path] = []
    negatives: list[Path] = []
    for img in sorted(img_dir.iterdir()):
        if img.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp"}:
            continue
        lines = remap_label(lbl_dir / f"{img.stem}.txt")
        if lines:
            positives.append(img)
        else:
            negatives.append(img)
    return positives, negatives


def write_yaml() -> None:
    yaml = DST / "data.yaml"
    path = str(DST.resolve()).replace("\\", "/")
    yaml.write_text(
        (
            f"path: {path}\n"
            "train: images/train\n"
            "val: images/val\n"
            "nc: 3\n"
            "names:\n"
            "  0: ambulance\n"
            "  1: fire_truck\n"
            "  2: police\n"
        ),
        encoding="utf-8",
    )


def main() -> None:
    if DST.exists():
        shutil.rmtree(DST)
    rng = random.Random(42)

    train_pos, train_neg = collect("train")
    val_pos, val_neg = collect("valid")
    rng.shuffle(train_pos)
    rng.shuffle(train_neg)
    rng.shuffle(val_pos)
    rng.shuffle(val_neg)

    train_imgs = train_pos[:TRAIN_POS_CAP] + train_neg[:TRAIN_NEG_CAP]
    val_imgs = val_pos[:VAL_POS_CAP] + val_neg[:VAL_NEG_CAP]
    rng.shuffle(train_imgs)
    rng.shuffle(val_imgs)

    print(f"[Compact] source train pos/neg = {len(train_pos)}/{len(train_neg)}")
    print(f"[Compact] source valid pos/neg = {len(val_pos)}/{len(val_neg)}")

    # copy_set needs original split folder name for labels
    img_out_train = DST / "images" / "train"
    lbl_out_train = DST / "labels" / "train"
    img_out_val = DST / "images" / "val"
    lbl_out_val = DST / "labels" / "val"
    for d in (img_out_train, lbl_out_train, img_out_val, lbl_out_val):
        d.mkdir(parents=True, exist_ok=True)

    box_counts: Counter = Counter()

    def copy_one(img: Path, split_name: str, src_split: str) -> None:
        lines = remap_label(SRC / src_split / "labels" / f"{img.stem}.txt")
        shutil.copy2(img, DST / "images" / split_name / img.name)
        (DST / "labels" / split_name / f"{img.stem}.txt").write_text(
            "\n".join(lines) + ("\n" if lines else ""), encoding="utf-8"
        )
        for line in lines:
            box_counts[(split_name, int(line.split()[0]))] += 1
        if not lines:
            box_counts[(split_name, "neg")] += 1

    for img in train_imgs:
        copy_one(img, "train", "train")
    for img in val_imgs:
        copy_one(img, "val", "valid")

    write_yaml()
    names = {0: "ambulance", 1: "fire_truck", 2: "police"}
    print(f"[Compact] copied train={len(train_imgs)} val={len(val_imgs)}")
    for split in ("train", "val"):
        for cid, name in names.items():
            print(f"  {split} {name} boxes={box_counts[(split, cid)]}")
        print(f"  {split} negatives={box_counts[(split, 'neg')]}")
    print(f"[Compact] yaml -> {DST / 'data.yaml'}")


if __name__ == "__main__":
    main()
