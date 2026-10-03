import os
import json
from pathlib import Path
from fastapi import APIRouter
from backend.config import BASE_DIR, DATASET_DIR, MODELS_DIR, load_config

router = APIRouter(prefix="/api/model", tags=["Model"])


@router.get("/status")
def get_model_and_dataset_status():
    config = load_config()

    # 1. Dataset Status
    raw_images_dir = BASE_DIR / "DETRAC-Images"
    raw_xml_train = BASE_DIR / "DETRAC-Train-Annotations-XML"
    raw_xml_test = BASE_DIR / "DETRAC-Test-Annotations-XML"

    # Also check if user moved them to dataset/raw/
    alt_raw_images = DATASET_DIR / "raw" / "DETRAC-Images"
    alt_xml_train = DATASET_DIR / "raw" / "DETRAC-Train-Annotations-XML"
    alt_xml_test = DATASET_DIR / "raw" / "DETRAC-Test-Annotations-XML"

    images_path = raw_images_dir if raw_images_dir.exists() else (alt_raw_images if alt_raw_images.exists() else None)
    train_xml_path = raw_xml_train if raw_xml_train.exists() else (alt_xml_train if alt_xml_train.exists() else None)
    test_xml_path = raw_xml_test if raw_xml_test.exists() else (alt_xml_test if alt_xml_test.exists() else None)

    # Count sequences / images
    total_sequences = 0
    total_raw_images = 0
    if images_path and images_path.exists():
        # DETRAC-Images usually contains an inner DETRAC-Images or sequences
        inner = images_path / "DETRAC-Images"
        seq_dir = inner if inner.exists() else images_path
        subdirs = [d for d in seq_dir.iterdir() if d.is_dir()]
        total_sequences = len(subdirs)
        # Approximate or sample: each sequence is ~300-1000 frames (total ~80,000 in full dataset)
        total_raw_images = total_sequences * 600  # estimated full count or counted

    # Count XML annotations
    total_xmls = 0
    if train_xml_path and train_xml_path.exists():
        inner_xml = train_xml_path / "DETRAC-Train-Annotations-XML"
        xml_dir = inner_xml if inner_xml.exists() else train_xml_path
        total_xmls += len(list(xml_dir.glob("*.xml")))
    if test_xml_path and test_xml_path.exists():
        inner_xml = test_xml_path / "DETRAC-Test-Annotations-XML"
        xml_dir = inner_xml if inner_xml.exists() else test_xml_path
        total_xmls += len(list(xml_dir.glob("*.xml")))

    # Check Processed YOLO Dataset
    processed_dir = DATASET_DIR / "processed"
    train_img_dir = processed_dir / "images" / "train"
    val_img_dir = processed_dir / "images" / "val"
    test_img_dir = processed_dir / "images" / "test"

    train_count = len(list(train_img_dir.glob("*.jpg"))) if train_img_dir.exists() else 0
    val_count = len(list(val_img_dir.glob("*.jpg"))) if val_img_dir.exists() else 0
    test_count = len(list(test_img_dir.glob("*.jpg"))) if test_img_dir.exists() else 0

    dataset_available = (images_path is not None and images_path.exists()) or (train_count > 0)

    # 2. Model Status
    custom_model_file = MODELS_DIR / "best.pt"
    base_model_file = MODELS_DIR / "yolov8n.pt"

    has_custom = custom_model_file.exists() and custom_model_file.stat().st_size > 1000
    has_base = base_model_file.exists() and base_model_file.stat().st_size > 1000

    if has_custom:
        model_name = "best.pt (Fine-tuned UA-DETRAC)"
        model_status = "Custom Trained Model Loaded"
        active_file = str(custom_model_file)
    elif has_base:
        model_name = "yolov8n.pt"
        model_status = "Pretrained Model Loaded (Fine-tuning available)"
        active_file = str(base_model_file)
    else:
        model_name = "yolov8n.pt"
        model_status = "Pretrained YOLOv8n (Auto-downloaded upon start)"
        active_file = "yolov8n.pt"

    # 3. Model Training Metrics
    metrics_file = MODELS_DIR / "metrics.json"
    metrics = {
        "precision": "Not available",
        "recall": "Not available",
        "map50": "Not available",
        "map50_95": "Not available",
        "epochs_trained": "Not available",
        "last_trained": "Not available"
    }

    if metrics_file.exists():
        try:
            with open(metrics_file, "r") as f:
                saved_metrics = json.load(f)
                metrics.update(saved_metrics)
        except Exception:
            pass

    return {
        "dataset": {
            "name": "UA-DETRAC Benchmark Dataset",
            "status": "Available" if dataset_available else "Missing / Not Downloaded",
            "sequences_count": total_sequences,
            "estimated_raw_images": total_raw_images,
            "annotations_xml_count": total_xmls,
            "processed_splits": {
                "train": train_count,
                "val": val_count,
                "test": test_count,
                "yaml_created": (processed_dir / "data.yaml").exists()
            }
        },
        "model": {
            "architecture": "YOLOv8n (Nano)",
            "active_model": model_name,
            "status": model_status,
            "file_path": active_file,
            "is_custom_trained": has_custom,
            "confidence_threshold": config.confidence_threshold,
            "iou_threshold": config.iou_threshold,
            "target_classes": ["car", "van", "bus", "others"] if has_custom else ["car", "motorcycle", "bus", "truck"]
        },
        "metrics": metrics
    }
