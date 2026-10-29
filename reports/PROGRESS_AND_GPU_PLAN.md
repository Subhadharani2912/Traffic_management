# Traffic Management — Implementation Status and GPU Training Plan

Date: 11 October 2026  
Project: `Traffic_management` (AI Adaptive Traffic Management System)

## Goal (confirmed)

1. Detect an **ambulance** (also fire truck / police when present).
2. Assign it to a lane: NORTH / SOUTH / EAST / WEST.
3. **Preempt** the signal so that approach gets green (after a safe yellow and all-red), then resume normal adaptive control.

Stock Ultralytics YOLOv8 (`yolov8n.pt`) **cannot** do step 1. COCO has car / bus / truck / motorcycle only. Roboflow Universe has hosted emergency models, but **not** a downloadable `.pt` for this local app. Therefore a **custom trained** `models/emergency_best.pt` is required.

---

## What is complete

### Application (usable today)

| Area | Status | Notes |
|---|---|---|
| FastAPI backend + React dashboard | Done | Live WebSocket monitoring, signals, analytics, reports |
| Four-way simulation | Done | Adaptive green from density + waiting + starvation |
| Real video pipeline | Done | YOLO detect + track + lane assignment |
| Path / crash fixes | Done | Relative model paths, `_simulation_loop(gen)` fix, launchers |
| Unit tests | Done | Adaptive logic + emergency preemption / confirmation tests |

### Emergency pipeline (code complete, model missing)

The app already implements the full ambulance path:

1. `backend/detection/detector.py` — second YOLO for `ambulance`, `fire_truck`, `police`. Loads `models/emergency_best.pt` if present; otherwise returns **no** emergency boxes (does not fake detections).
2. `backend/detection/tracker.py` — 5 consecutive frames before `emergency_active`.
3. `backend/traffic/signal_controller.py` — `preempt_emergency()`: if that lane is already green, hold it; else GREEN → YELLOW → ALL-RED → emergency GREEN (~15 s). Only one green at a time.
4. `backend/services/video_processor.py` — every frame: `detect_emergency` → confirm → preempt that direction.

**Improvement vs original clone:** emergency is a real modular detector + safety preemption, not a comment. Indian class aliases (`ambulance_108`, `ambulance_SOL`) map to `ambulance`.

### Dataset work

- Indian Roboflow emergency export prepared under `dataset/emergency_indian`.
- `scripts/prepare_indian_emergency.py` remaps 24 noisy classes down to **3 vehicle classes** and can build `dataset/emergency_compact`.
- `scripts/train.py --emergency` writes best weights to `models/emergency_best.pt`.

### CPU training (attempted, not successful)

This PC: **Intel UHD Graphics**, PyTorch `cuda: False`, no NVIDIA driver.

| Run | Settings | Outcome |
|---|---|---|
| `emergency_training` | CPU, batch 4, imgsz 416, 15% of data, 30 epochs planned | Too slow / incomplete |
| `emergency_training_fast` | CPU, batch 8, imgsz 320, 8% of data, freeze 10 | CPU workaround, not a real model |

`models/emergency_best.pt` is **not** present. Validation on `Emergency_Ambulance.mp4`: **0 / 97** sampled frames detected ambulance. `Traffic.mp4`: 0 false positives (empty detector).

---

## What is not done

- Train a usable ambulance YOLO (needs GPU).
- Plug `emergency_best.pt` and prove preemption on `Emergency_Ambulance.mp4`.
- Optional later: fire/police accuracy, more Indian CCTV footage.

Until weights exist, the dashboard can still run **normal** traffic detection and adaptive signals. It will **not** identify an ambulance.

---

## Next steps on a GPU server

A CUDA GPU (Colab T4, RTX 3060+, or any NVIDIA cloud box) is enough. YOLOv8n does not need a high-end card.

### 1. Environment

- NVIDIA driver + CUDA PyTorch (`torch.cuda.is_available()` must be True).
- Copy this project, or at least: `scripts/train.py`, `dataset/emergency_compact` (or `emergency_indian`), `requirements.txt`.

### 2. Train (full data, no CPU `--fraction`)

```bash
python scripts/train.py --emergency --device 0 --batch 16 --epochs 50 --imgsz 640 --patience 15
```

- If VRAM ≥ 16 GB: `--batch 32`.
- Prefer `dataset/emergency_compact` (3 classes). If missing, run `python scripts/prepare_indian_emergency.py` first.
- Output: `models/emergency_best.pt` (copied from the Ultralytics run folder by `train.py`).

### 3. Bring weights back to this PC

Copy `emergency_best.pt` to:

`Traffic_management/models/emergency_best.pt`

Config already points at that path (`emergency_model_path` in `backend/system_config.json`). No detector rewrite.

### 4. Verify

```bash
python scripts/evaluate.py --emergency --data dataset/emergency_compact/data.yaml
```

Then run the app on `videos/input/Emergency_Ambulance.mp4`. Pass if:

- Ambulance boxes appear across frames.
- After 5 confirmed frames, **only that lane** goes green (after yellow / all-red).
- `Traffic.mp4` stays mostly free of false ambulances.

---

## Bottom line

| Question | Answer |
|---|---|
| Is the traffic system implemented? | Yes — control, video, dashboard. |
| Can it identify an ambulance today? | No — missing trained weights. |
| Did we improve the project? | Yes — emergency architecture, Indian data, safe preemption, CPU/GPU train flags. |
| Is a GPU server worth it? | Yes — that is the remaining critical step. |
| Must we re-code after GPU training? | No — drop in `emergency_best.pt`. |
