# AI Adaptive Traffic Management System

A complete local traffic control project inspired by a four-way intersection reference video. The project combines Python FastAPI backend services, YOLO-based vehicle detection, adaptive traffic signal logic, and a React dashboard.

## Project Objective

This system is intended to:
- accept a real traffic video or run a simulation,
- detect vehicles using YOLO,
- track vehicles across frames,
- assign each vehicle to a direction (NORTH/SOUTH/EAST/WEST),
- compute density, waiting time, and priority,
- update traffic signals dynamically,
- display results on a professional real-time dashboard.

## Features

- Real traffic video upload and processing
- Four-way intersection simulation
- YOLOv8 detection + tracking
- Adaptive signal priority logic
- Density analysis and waiting-time estimation
- SQLite analytics and logs
- Dashboard and live monitoring interface
- Dataset and model status page
- Training and evaluation scripts

## Project Structure

```text
Traffic_Management_System/
├── backend/
│   ├── app.py
│   ├── config.py
│   ├── database/
│   ├── detection/
│   ├── routes/
│   ├── services/
│   ├── traffic/
│   └── websocket/
├── dataset/
│   ├── raw/
│   └── processed/
├── frontend/
├── models/
├── reports/
├── scripts/
│   ├── prepare_dataset.py
│   ├── train.py
│   └── evaluate.py
├── videos/
│   ├── input/
│   └── output/
├── requirements.txt
├── README.md
└── .gitignore
```

## Technology Stack

- Python 3.13
- FastAPI
- OpenCV
- Ultralytics YOLOv8
- SQLite
- React + Vite
- NumPy / Pandas

## Setup

### 1. Backend

```powershell
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r ..\requirements.txt
python app.py
```

The backend runs on:
- http://localhost:8000

### 2. Frontend

```powershell
cd frontend
npm install
npm run dev
```

The dashboard runs on:
- http://localhost:5173

## Dataset Preparation

The project expects the UA-DETRAC data to be available under the workspace root or inside the `dataset/raw/` directory.

### Example locations

```text
DETRAC-Images/
DETRAC-Train-Annotations-XML/
DETRAC-Test-Annotations-XML/
```

Then run:

```powershell
python scripts\prepare_dataset.py
```

This creates the processed YOLO-ready dataset in:

```text
dataset/processed/images/train
dataset/processed/images/val
dataset/processed/images/test
```

## Model Training

```powershell
python scripts\train.py --epochs 10 --imgsz 640 --batch 8
```

A trained output may be saved as:

```text
models\best.pt
```

If no trained model exists, the app will still operate with the pretrained YOLOv8n model.

## Adaptive Signal Control

The system uses the same logic for both simulation and video-processing modes:

- count vehicles by direction,
- compute density from count thresholds,
- estimate waiting time by speed and red signal state,
- compute priority using density + waiting time + starvation prevention,
- choose the next green phase,
- assign dynamic green duration within configured min/max values.

## Configuration

The main configuration is stored in:

```text
backend/config.py
```

Key settings include:
- detection confidence threshold,
- IoU threshold,
- min and max green time,
- yellow time,
- density and waiting weights,
- waiting-speed threshold,
- ROI boxes for NORTH/SOUTH/EAST/WEST.

## Uploading a Video

Use the frontend upload control or place a video in:

```text
videos/input/
```

Allowed video files include:
- .mp4
- .avi
- .mov
- .mkv

## Database

The project uses SQLite for traffic statistics and system events:

```text
backend/database/traffic.db
```

## Testing

The project includes lightweight logic-level checks for:
- vehicle counting,
- density calculation,
- waiting-time estimation,
- priority scoring,
- green-duration calculation,
- signal state transitions.

You can run tests with:

```powershell
pytest
```

## Notes

- This project is designed to work locally on Windows.
- The final model training is optional; the app can run with a pretrained YOLO model.
- Real detection performance depends on the available dataset and computer hardware.

## Future Enhancements

- real-time camera integration,
- export reports as PDF/CSV,
- stronger tracking with ByteTrack tuning,
- improved ROI calibration UI,
- better historical analytics graphs.
