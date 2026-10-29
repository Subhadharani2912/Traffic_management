#!/usr/bin/env python3
"""
Real-Video Emergency Vehicle Detector Validation Script (Phase 3).
Validates:
  1. Emergency Video: videos/input/Emergency_Ambulance.mp4
  2. Normal Video:    videos/input/Traffic.mp4

Measures:
  - Total frames processed
  - Emergency vehicle detections (ambulance, fire_truck, police)
  - False positive count & rate on normal traffic footage
  - Detection consistency across sequential frames (temporal persistence)
  - Processing speed (FPS)
"""
import time
import json
import sys
from pathlib import Path
import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
VIDEOS_DIR = ROOT / "videos" / "input"
from backend.detection.detector import VehicleDetector


def validate_video(detector: VehicleDetector, video_path: Path, is_emergency_expected: bool, sample_stride: int = 5):
    if not video_path.exists():
        return {"error": f"Video not found: {video_path}"}

    cap = cv2.VideoCapture(str(video_path))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    video_fps = cap.get(cv2.CAP_PROP_FPS) or 25.0

    print(f"\n=======================================================")
    print(f"Validating: {video_path.name}")
    print(f"Total Frames: {total_frames} | Video FPS: {video_fps:.1f} | Expected Emergency: {is_emergency_expected}")
    print(f"=======================================================")

    frames_sampled = 0
    emergency_hits = 0
    detected_classes = {"ambulance": 0, "fire_truck": 0, "police": 0}
    max_consecutive_hits = 0
    current_consecutive_hits = 0
    latencies = []

    f_idx = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if f_idx % sample_stride == 0:
            frames_sampled += 1
            t0 = time.time()
            em_dets = detector.detect_emergency(frame, conf=0.35)
            dt = time.time() - t0
            latencies.append(dt)

            if em_dets:
                emergency_hits += 1
                current_consecutive_hits += 1
                if current_consecutive_hits > max_consecutive_hits:
                    max_consecutive_hits = current_consecutive_hits

                for d in em_dets:
                    cname = d["class_name"]
                    detected_classes[cname] = detected_classes.get(cname, 0) + 1
                    if f_idx % 25 == 0:
                        print(f"  Frame {f_idx:04d}: DETECTED {cname.upper()} (conf: {d['confidence']:.2f}, bbox: {d['bbox']})")
            else:
                current_consecutive_hits = 0

        f_idx += 1

    cap.release()

    avg_latency = sum(latencies) / len(latencies) if latencies else 0.0
    inference_fps = (1.0 / avg_latency) if avg_latency > 0 else 0.0

    hit_rate = (emergency_hits / frames_sampled * 100.0) if frames_sampled > 0 else 0.0

    results = {
        "video": video_path.name,
        "is_emergency_video": is_emergency_expected,
        "total_video_frames": total_frames,
        "frames_sampled": frames_sampled,
        "emergency_detections_count": emergency_hits,
        "detection_rate_pct": round(hit_rate, 2),
        "class_breakdown": detected_classes,
        "max_consecutive_confirmed_frames": max_consecutive_hits,
        "five_frame_confirmed": max_consecutive_hits >= 5,
        "avg_latency_ms": round(avg_latency * 1000, 1),
        "avg_inference_fps": round(inference_fps, 1),
    }

    if is_emergency_expected:
        results["evaluation"] = {
            "missed_detections_sampled_frames": frames_sampled - emergency_hits,
            "detection_sensitivity": f"{hit_rate:.1f}%",
            "sustained_confirmation": "PASSED (>= 5 consecutive frames)" if max_consecutive_hits >= 5 else "MARGINAL"
        }
    else:
        results["evaluation"] = {
            "false_positives": emergency_hits,
            "false_positive_rate": f"{hit_rate:.2f}%",
            "purity": "100% CLEAN" if emergency_hits == 0 else f"{100.0 - hit_rate:.1f}%"
        }

    print("\nResults Summary:")
    print(json.dumps(results, indent=2))
    return results


def main():
    detector = VehicleDetector(emergency_model_path="models/emergency_best.pt")
    print(f"[Detector Status] Primary: {detector.model_status}")
    print(f"[Detector Status] Emergency: {detector.emergency_model_status} | Map: {detector.active_emergency_map}")

    reports = []
    # 1. Test Emergency Video
    em_vid = VIDEOS_DIR / "Emergency_Ambulance.mp4"
    if em_vid.exists():
        reports.append(validate_video(detector, em_vid, is_emergency_expected=True, sample_stride=3))

    # 2. Test Normal Traffic Video
    norm_vid = VIDEOS_DIR / "Traffic.mp4"
    if norm_vid.exists():
        reports.append(validate_video(detector, norm_vid, is_emergency_expected=False, sample_stride=4))

    # Save validation summary
    out_file = ROOT / "reports" / "emergency_model_validation.json"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(reports, f, indent=2)
    print(f"\n[Saved Full Validation Report] {out_file}")


if __name__ == "__main__":
    main()
