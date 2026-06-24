# LabLens

A gesture-controlled chemistry lab built with OpenCV and MediaPipe. LabLens allows students to "load" virtual chemicals onto their fingertip using hand tracking and drop them into a virtual beaker to trigger realistic, animated chemical reactions. It also includes a secondary simplified Periodic Table mode.

## Setup

1. Clone the repository
2. Create a virtual environment:
   ```bash
   python -m venv venv
   .\venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Optional: Export your Anthropic API Key to use the AI Examiner feature:
   ```bash
   $env:ANTHROPIC_API_KEY="your-api-key-here"
   ```
5. Run the application:
   ```bash
   python main.py
   ```

*Note: The SQLite database (`lablens.db`) will be automatically seeded with 20 reactions and ~22 elements the first time you run the app.*

## Controls & Gestures

LabLens relies heavily on hand tracking to interact with the environment. Make sure you use a single hand in view, with decent lighting.

| Action / Gesture | Effect |
| :--- | :--- |
| **Hover tube icon (top-left)** | Opens the Reagent Selector popup |
| **Hover basket icon (bottom-right)** | Opens the Equipment Bar popup |
| **DIP (enter chemical pill)** | "Loads" the hovered chemical onto your fingertip |
| **COMBINE (move into Beaker)** | Drops the loaded chemical into the beaker |
| **WASH OFF (open palm swipe)** | Unloads the currently loaded chemical from your finger |
| **FIST** | Toggles between Reaction Lab and Periodic Table modes, AND resets the beaker if in Lab mode |
| **Hover (in Periodic Table)** | Shows a tooltip for the hovered element |
| **Hold > 1.5s (in Periodic Table)** | Opens a detailed Character Card for the element |
| **Press 'a' (keyboard)** | Triggers the AI Examiner (after a reaction) |
| **Press 'f' (keyboard)** | Toggles fullscreen |
| **Press 'q' (keyboard)** | Quits the application |

## Known Limitations

- **Lighting Sensitivity**: MediaPipe hand tracking performs best in well-lit environments. Poor lighting may cause jittery fingertips or missed gestures.
- **Single-Hand Only**: The app tracks exactly one hand (the first one detected). Using two hands may cause the tracker to jump between them.
- **Limited Reactions**: The current database has been seeded with a subset of 20 standard NCERT/JEE inorganic chemistry reactions.
- **No Complex Equipment**: Apparatus like bunsen burners are currently aesthetic only; heat/conditions are handled automatically if the reaction matches.
