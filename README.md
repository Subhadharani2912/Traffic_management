# Adaptive Traffic Management System with Emergency Vehicle Priority

An intelligent traffic management application that combines computer vision, vehicle tracking, and adaptive signal control to improve traffic flow at a four-way intersection. The system supports traffic video analysis and a simulation mode, with a React dashboard for monitoring traffic conditions and signal decisions.

A key focus of this project is **emergency vehicle detection and priority handling**, allowing the system to incorporate emergency vehicles into its traffic-control decisions.

## Project Overview

Conventional traffic signals often rely on fixed timing, which may not reflect actual traffic conditions. This project explores a software-based approach in which traffic density, estimated waiting time, and vehicle priority are used to determine signal phases dynamically.

The application integrates a Python backend, YOLO-based computer vision, traffic-control logic, and a web-based monitoring interface.

## Key Capabilities

- **Emergency vehicle recognition:** Uses a custom-trained YOLO model to identify supported emergency vehicle categories.
- **Video-based traffic analysis:** Processes uploaded traffic videos and detects vehicles across video frames.
- **Vehicle tracking:** Maintains vehicle tracks to support traffic analysis over time.
- **Four-direction traffic management:** Organizes traffic information by NORTH, SOUTH, EAST, and WEST.
- **Adaptive signal decisions:** Selects signal phases based on traffic conditions and configured priority rules.
- **Waiting-time estimation:** Estimates how long vehicles have been waiting under red-signal conditions.
- **Emergency priority handling:** Integrates emergency vehicle detection with traffic-control decisions.
- **Interactive dashboard:** Displays traffic information, detection results, and signal states through a React interface.
- **Traffic reports and analytics:** Supports the project's reporting and statistical analysis features.
- **Simulation mode:** Enables traffic-control logic to be tested without relying exclusively on real traffic footage.

*Note: Detection accuracy and emergency-response behavior depend on model performance, video quality, lane configuration, and the current system settings.*

## System Architecture

The project is organized into three main components:

| Component | Responsibility |
|---|---|
| Computer vision | Detects vehicles and processes detection results from video frames. |
| Traffic management backend | Handles traffic analysis, priority calculations, signal decisions, and related services. |
| Web dashboard | Presents traffic conditions, detection information, signal controls, and reports. |

## Technology Stack

**Backend**
- Python
- FastAPI
- OpenCV
- Ultralytics YOLO
- SQLite

**Frontend**
- React
- Vite
- JavaScript
- CSS

**Machine Learning and Evaluation**
- YOLO-based object detection
- Custom emergency vehicle model
- Training and evaluation scripts
- Pytest for logic-level testing

## Repository Structure

```text
Traffic_Management/
├── backend/
│   ├── database/
│   ├── detection/
│   ├── routes/
│   ├── services/
│   ├── traffic/
│   ├── tests/
│   ├── config.py
│   └── system_config.json
├── frontend/
│   └── src/
│       ├── panels/
│       ├── App.jsx
│       └── api.js
├── models/
│   ├── emergency_best.pt
│   └── emergency_colab_best.pt
├── reports/
├── scripts/
│   ├── evaluate.py
│   └── train.py
├── requirements.txt
├── pytest.ini
└── README.md
```

*The structure above highlights the main project components; additional files and directories may exist in the repository.*

## Running the Application

### 1. Start the Backend

Open a terminal in the project root and activate your Python environment.

```powershell
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r ..\requirements.txt
```

Start the backend using the entry point configured in your project. For example, if the application exposes `app` from `app.py`:

```powershell
uvicorn app:app --reload
```

Backend address, if configured to use the default port:

`http://localhost:8000`

### 2. Start the Frontend

Open a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

The Vite development server commonly runs at:

`http://localhost:5173`

Confirm the actual backend entry point and configured ports in your local project before running these commands.

## Emergency Vehicle Detection

The project includes a custom-trained YOLO model intended to recognize these emergency vehicle classes:

- Ambulance
- Fire truck
- Police vehicle

The model is integrated into the detection pipeline so that its results can contribute to emergency-priority handling.

Detection results should be evaluated against representative traffic videos before claiming reliable real-world performance. Small or distant emergency vehicles, occlusion, lighting conditions, and camera angles can affect recognition.

## Adaptive Traffic Signal Logic

The traffic-control component uses traffic information and configurable rules to make signal decisions.

The intended processing flow is:

1. Obtain vehicle detections from video processing or simulation.
2. Associate vehicles with configured intersection directions.
3. Estimate directional traffic density.
4. Estimate waiting time where applicable.
5. Calculate priority using the configured traffic-management rules.
6. Consider emergency priority and starvation prevention.
7. Select the next signal phase and determine its green duration within configured limits.
8. Update the dashboard with the resulting traffic and signal information.

The exact behavior is controlled by the project's backend configuration and signal-control implementation.

## Configuration

Traffic-control and detection parameters are managed through the backend configuration files.

Depending on the current implementation, these settings include:

- Model paths and detection confidence thresholds
- Emergency vehicle class configuration
- Intersection lane regions
- Traffic-density thresholds
- Waiting-time and priority parameters
- Minimum and maximum green durations
- Signal transition settings

Review `backend/config.py` and `backend/system_config.json` for the configuration supported by your current version.

## Training and Evaluation

The repository includes scripts for model training and evaluation.

Example commands, subject to the arguments supported by the scripts:

```powershell
python scripts/train.py
python scripts/evaluate.py
```

Check each script's command-line options before specifying training parameters. The trained weights and evaluation results depend on the dataset, configuration, and training run.

## Testing

Run the project's logic-level tests from the repository root:

```powershell
pytest
```

These tests can help verify traffic-control behavior, including calculations and signal transitions covered by the existing test suite.

Passing logic-level tests does not, by itself, establish that emergency vehicles will be detected reliably in real-world videos.

## Current Scope and Limitations

- The application supports software-based traffic analysis and simulation.
- Emergency vehicle recognition depends on the trained model and the quality of the input footage.
- Direction assignment depends on the configured intersection regions.
- Real-world traffic conditions may require further model evaluation and parameter tuning.
- Hardware integration, if used in a separate prototype, is distinct from the software pipeline described here.

## Future Improvements

- Improve emergency vehicle detection across different traffic conditions.
- Evaluate model performance using a broader collection of real traffic videos.
- Refine lane-region calibration and vehicle tracking.
- Expand historical traffic analytics and performance comparisons.
- Improve signal decisions for complex or simultaneous emergency scenarios.
- Explore integration with live camera feeds and physical traffic-signal hardware.
