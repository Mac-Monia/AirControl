# AirControl

AirControl is a Python application that lets you control your computer hands-free with gestures captured by your webcam: move the cursor, click, right-click, double-click, scroll, drag and drop, zoom, swipe between pages, control media and run presentations.

It uses MediaPipe for real-time hand landmark detection, OpenCV for webcam capture and on-screen feedback, and PyAutoGUI for mouse and keyboard control.

## Features

**Pointing and clicking**

- **Cursor control:** Move the cursor with your index fingertip.
- **Adaptive smoothing:** A One Euro filter keeps the cursor steady when your hand is still and responsive when it moves fast. The cursor glides on its own thread between camera frames.
- **Click:** Pinch your thumb and index finger together. The cursor freezes as your fingers close, so the click lands where you aimed.
- **Double-click:** Pinch twice quickly. After a click the cursor holds still briefly so the second click lands on the same spot.
- **Right-click:** Keep your index finger up and pinch your thumb and middle finger together.

**Gestures**

- **Scroll:** Make a peace sign and move your hand up or down.
- **Drag and drop:** Open your palm, close your fist to grab, open your palm to drop.
- **Zoom:** Pinch with both hands, then move them apart or together.
- **Swipe:** Raise three fingers and flick left, right, up or down.
- **Media controls:** Thumbs up plays or pauses in any app. In the media profile, swipes change the track and the volume.
- **Presentation controls:** In the slides profile, swipes move between slides and start or end the slideshow.
- **Navigation:** In the navigate profile, swipes go back, forward and between tabs.

**Reliability and control**

- **Accidental-action prevention:** Gestures must be held for several frames, and some must be held for a set time. Thresholds differ for starting and releasing a gesture. Pinches are ignored right after another mode, and held poses are ignored when your hand is partly out of view.
- **Feedback:** The camera window shows the current mode, the last action, a progress bar for held gestures, warnings, a help overlay (`H`) and a debug view (`D`).
- **Calibration and sensitivity:** Pinch calibration (`C`), reach calibration (`R`), and live sensitivity (`+`/`-`) and smoothing (`[`/`]`) adjustment, all saved between runs.
- **Configurable gestures:** Assign swipes, thumbs up and the rock sign to any keys, hotkeys, mouse actions or profile switches in `settings.json`, and override any tuning value.
- **Safety:** Hold both palms open to pause or resume. `Ctrl+Alt+P` pauses and `Ctrl+Alt+Q` quits from any window (Windows). The PyAutoGUI fail-safe stays on, and held mouse buttons are always released.
- **Error handling:** If the camera stops sending frames, AirControl reconnects automatically and releases any drag. It warns about low light and a hand at the edge of the frame. Bad settings produce warnings instead of crashes.
- **Performance:** Camera capture runs on its own thread, so hand tracking always uses the newest frame. The window shows FPS and processing time.

## Requirements

- Python 3.9–3.12
- A webcam
- A desktop environment that supports mouse control (developed and tested on Windows; global hotkeys and the system double-click time are Windows-only)

## Installation

```bash
git clone https://github.com/Mac-Monia/AirControl.git
cd AirControl
python -m venv .venv
```

Activate the virtual environment:

```powershell
.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, use Command Prompt instead: `.venv\Scripts\activate.bat`.

Install the dependencies:

```bash
python -m pip install -r requirements.txt
```

## Usage

```bash
python main.py
```

Hold your hand 40–80 cm from the webcam, palm facing the camera, in good light. The magenta rectangle shows the area of the camera view that maps to your screen.

### Gestures

| Gesture | Action |
| --- | --- |
| Point with your index finger | Move the cursor |
| Pinch thumb + index | Click |
| Pinch thumb + index twice quickly | Double-click |
| Index finger up, pinch thumb + middle | Right-click |
| Peace sign (index + middle up), move up/down | Scroll |
| Open palm → close fist → open palm | Grab, move, drop |
| Pinch with both hands, move apart/together | Zoom in/out (Ctrl + mouse wheel) |
| Three fingers up (index, middle, ring), flick | Swipe (depends on the profile) |
| Thumbs up, hold | Play/pause (black screen in the slides profile) |
| Index + pinky up (rock sign), hold | Switch to the next profile |
| Both palms open, hold about 1 second | Pause / resume AirControl |

A fist on its own does nothing, so curling your hand never clicks or grabs by accident. Swipe directions follow your hand as you see it in the mirrored camera window. Swiping left means "next", as on a touchscreen.

### Profiles

Swipes and held poses change meaning with the active profile, shown at the top right of the camera window. Switch profiles with the rock sign or the `M` key.

| Profile | Swipe left | Swipe right | Swipe up | Swipe down | Thumbs up |
| --- | --- | --- | --- | --- | --- |
| `navigate` | Forward (Alt+→) | Back (Alt+←) | Next tab | Previous tab | Play/pause |
| `media` | Next track | Previous track | Volume up | Volume down | Play/pause |
| `slides` | Next slide (→) | Previous slide (←) | Start slideshow (Shift+F5) | End slideshow (Esc) | Black screen (B) |

The slideshow keys suit PowerPoint. Change them in `settings.json` for other apps.

### Keys

These keys work when the camera window is focused.

| Key | Action |
| --- | --- |
| `H` | Show or hide the gesture and key help |
| `P` | Pause / resume |
| `M` | Next profile |
| `+` / `-` | More / less cursor sensitivity |
| `[` / `]` | Steadier / snappier cursor |
| `0` | Reset sensitivity and smoothing |
| `C` | Calibrate the pinch |
| `R` | Calibrate your reach |
| `D` | Show or hide the debug view |
| `L` | Show or hide hand landmarks |
| `Q` / `Esc` | Quit |

On Windows, `Ctrl+Alt+P` (pause) and `Ctrl+Alt+Q` (quit) work from any window.

### Calibration (recommended on first run)

**Pinch (`C`):** follow the prompts in the camera window.

1. Point with your index finger, thumb relaxed (2.5 seconds).
2. Pinch your thumb and index finger together (2.5 seconds).

This sets the click thresholds for your hand. Recalibrate if clicks trigger too early or too late.

**Reach (`R`):** for 6 seconds, trace the edges of the area your index finger can comfortably cover. A green box shows the area covered so far, and that area then maps to the whole screen. This suits your arm, your seating position and your screen size.

Calibration, sensitivity and smoothing are saved to `calibration.json` and load automatically next time.

### Stopping

- Press `Q` or `Esc` in the camera window, or close the window.
- Press `Ctrl+Alt+Q` from anywhere (Windows).
- Emergency stop: move the mouse to the top-left corner of the screen to trigger PyAutoGUI's fail-safe.

## Configuration

Copy `settings.example.json` to `settings.json` and edit it. Anything you leave out keeps its default. `settings.json` is personal and is not committed.

```json
{
  "profile": "slides",
  "tuning": {
    "SCROLL_SPEED": 3500,
    "CAMERA_INDEX": 1
  },
  "gestures": {
    "media": {
      "swipe_up": {"action": "volumeup*10", "label": "Volume up more"}
    },
    "slides": {
      "swipe_up": "ctrl+f5"
    }
  }
}
```

- **`profile`:** the profile to start in.
- **`tuning`:** overrides any number or true/false constant at the top of `main.py`. Values that should be whole numbers must stay whole.
- **`gestures`:** maps `swipe_left`, `swipe_right`, `swipe_up`, `swipe_down`, `thumbs_up` and `rock` to an action, per profile. Entries under `all` apply in every profile unless the profile sets the same gesture. Add a new name to create a new profile.

Each gesture maps either to an action text or to an object with an `action` and a `label` (the text shown on screen). Action texts:

| Action | Example | Meaning |
| --- | --- | --- |
| Key | `"space"`, `"pagedown"`, `"playpause"` | Press a key (any PyAutoGUI key name) |
| Hotkey | `"ctrl+shift+tab"` | Press keys together |
| Repeat | `"volumeup*5"` | Press several times |
| Mouse | `"mouse:right"`, `"mouse:double"` | Click (`left`, `right`, `middle`, `double`) |
| Profile | `"profile:next"`, `"profile:media"` | Switch profile (`next`, `previous` or a name) |
| Pause | `"pause"` | Pause AirControl |
| Nothing | `"none"` | Disable the gesture |

Invalid entries are reported in the terminal at startup and skipped.

### Common tuning values

| Parameter | Description |
| --- | --- |
| `CAMERA_INDEX` | Which webcam to use (0 = default). |
| `MODEL_COMPLEXITY` | 1 = more accurate, 0 = faster. Use 0 if the FPS is below about 20. |
| `FRAME_MARGIN_X/Y` | Default frame border excluded from screen mapping (before reach calibration). |
| `MIN_CUTOFF` | Smoothing when the hand is still (lower = less jitter). |
| `BETA` | Responsiveness during fast movement (higher = less lag). |
| `CURSOR_GLIDE` | How quickly the cursor glides to its target (lower = snappier). |
| `PINCH_START` / `PINCH_RELEASE` | Pinch ratios that start and release a pinch (set by calibration). |
| `FREEZE_RATIO` | Pinch ratio below which the cursor stops moving to aim a click. |
| `PINCH_FRAMES_REQUIRED` | Frames a pinch must be held to click. |
| `CLICK_COOLDOWN` | Minimum seconds between clicks. |
| `DOUBLE_CLICK_TIME` | Seconds the cursor holds still after a click (0 = system setting). |
| `MIDDLE_REACH_RATIO` | How far the middle finger must reach out for a right-click pinch. |
| `MODE_SETTLE_TIME` | Seconds pinches are ignored after leaving another mode. |
| `SCROLL_SPEED` / `SCROLL_INVERT` | Scroll speed and direction. |
| `ZOOM_STEP` / `ZOOM_INVERT` | Hand movement per zoom step, and zoom direction. |
| `SWIPE_DISTANCE` / `SWIPE_WINDOW` | How far (in hand sizes) and how fast a swipe must be. |
| `SWIPE_COOLDOWN` / `SWIPE_REVERSE_BLOCK` | Pause before the next swipe, and before an opposite swipe. |
| `POSE_HOLD_TIME` / `PROFILE_HOLD_TIME` / `PAUSE_HOLD_TIME` | How long held poses must be held. |
| `THUMB_OUT_RATIO` | How far the thumb must stick out for a thumbs up. |
| `FINGER_EXTENDED_RATIO` | How straight a finger must be to count as raised. |
| `LOW_LIGHT_LEVEL` | Brightness below which the low light warning shows. |
| `ALWAYS_ON_TOP` | Keep the camera window above other windows. |
| `GLOBAL_HOTKEYS` | Enable `Ctrl+Alt+P` / `Ctrl+Alt+Q` (Windows). |

## Troubleshooting

| Problem | Try |
| --- | --- |
| "Cannot open webcam" | Close other apps using the camera, or set `CAMERA_INDEX` to 1 or 2. |
| Cursor shakes when the hand is still | Press `[` a few times, improve lighting, or lower `MIN_CUTOFF`. |
| Cursor lags behind fast movements | Press `]`, or raise `BETA` gradually. |
| Can't reach the screen edges | Press `R` to calibrate your reach, or `+` for more sensitivity. |
| Clicks trigger too early, too late or not at all | Press `C` to calibrate the pinch. Watch the pinch ratio on screen. |
| Right-click doesn't trigger | Keep your index finger straight up and bring the middle fingertip to the thumb. Press `D` to check the finger states, or lower `MIDDLE_REACH_RATIO`. |
| Double-click doesn't register | Pinch faster, or raise the double-click speed setting in Windows mouse settings. |
| Swipes don't trigger | Flick faster, or lower `SWIPE_DISTANCE`. Make sure the status shows `SWIPE` first. |
| Gestures are misread | Press `D` to see how each finger is read (`+` up, `-` folded, `~` in between). Keep your palm facing the camera. |
| Low FPS or lag | Set `MODEL_COMPLEXITY` to 0, close other camera apps, and improve lighting (dim light lowers the camera frame rate). |
| "Low light" warning | Face a light source. Avoid a bright window behind you. |
| AirControl does something unexpected | Hold both palms open or press `Ctrl+Alt+P` to pause. |

## Testing

The gesture logic is covered by unit tests that use synthetic hand landmarks, so they need no webcam:

```bash
python -m unittest discover tests
```

To test gestures live, press `D` in the camera window. It shows the detected pose, each finger's state and the hand size. Use it to check how gestures are read under different lighting, distances and angles.

## Safety

AirControl controls your real mouse and keyboard.

- Keep the PyAutoGUI fail-safe enabled. Moving the mouse to the top-left corner stops AirControl.
- Pause AirControl (both palms, `P` or `Ctrl+Alt+P`) when you're not using it, and before sensitive operations.
- Mouse buttons held for dragging are released when you pause, lose tracking, lose the camera or quit.

## Project Structure

```text
AirControl/
├── main.py                  # Hand tracking, gestures and mouse/keyboard control
├── settings.example.json    # Example gesture and tuning settings
├── requirements.txt         # Python dependencies
├── tests/
│   └── test_gestures.py     # Unit tests for the gesture logic
├── README.md
└── .gitignore
```

`calibration.json` and `settings.json` are created locally and not committed.

## Contributing

Contributions, suggestions and bug reports are welcome. The most useful contributions are live testing under different lighting, cameras and hand sizes, and reports of gestures that are misread.

## License

No license has been specified yet.
