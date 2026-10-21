# AirControl

AirControl is a Python-based computer vision project that explores hands-free computer interaction by tracking hand movements through a webcam and translating index-fingertip movement into cursor movement.

The project is being developed step by step, with a focus on understanding the underlying concepts rather than simply assembling code.

## Features

- Real-time hand landmark detection using MediaPipe
- Index-fingertip tracking
- Webcam coordinate-to-screen coordinate mapping
- Cursor smoothing to reduce jitter
- Mouse control using PyAutoGUI
- Keyboard exit and PyAutoGUI fail-safe protection

## Tech Stack

- **Python** — application logic
- **OpenCV** — webcam capture and image processing
- **MediaPipe** — hand landmark detection
- **PyAutoGUI** — operating-system cursor control

## Getting Started

### Prerequisites

- Windows
- Python
- Git
- A working webcam

### Installation

1. Clone the repository:

   ```bash
   git clone YOUR_REPOSITORY_URL
   cd AirControl
   ```

2. Create a virtual environment:

   ```bash
   python -m venv .venv
   ```

3. Activate the environment in PowerShell:

   ```powershell
   .\.venv\Scripts\Activate.ps1
   ```

4. Install the required packages:

   ```bash
   python -m pip install mediapipe==0.10.21 opencv-contrib-python==4.11.0.86 pyautogui
   ```

5. Start the application:

   ```bash
   python main.py
   ```

Press **Q** while the webcam window is focused to exit.

## How It Works

1. OpenCV captures frames from the webcam.
2. The frame is mirrored and converted from BGR to RGB.
3. MediaPipe detects hand landmarks.
4. AirControl reads the index-fingertip coordinates.
5. Smoothing reduces rapid changes in fingertip position.
6. The coordinates are mapped to screen pixels.
7. PyAutoGUI moves the computer cursor.

## Roadmap

- [ ] Improve cursor calibration and sensitivity
- [ ] Display the control region in the webcam window
- [ ] Implement pinch-to-click
- [ ] Add more hand gesture controls


## Safety

AirControl moves the real system cursor. Keep PyAutoGUI's fail-safe enabled and test cursor movement carefully. Move the cursor to the top-left corner of the screen to trigger the fail-safe. Press Q in the webcam window to exit normally.

## Project Status

This project is under active development. Features listed in the roadmap have not necessarily been implemented yet.
