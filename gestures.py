import cv2
import mediapipe as mp
import numpy as np
from enum import Enum, auto
from dataclasses import dataclass
import time
from typing import Tuple, Optional, Any

class Gesture(Enum):
    NONE         = auto()
    HOVER        = auto()
    DIP          = auto()
    COMBINE      = auto()
    WASH_OFF     = auto()
    FIST         = auto()
    THREE_FINGERS = auto()  # index + middle + ring up, thumb + pinky folded

@dataclass
class GestureState:
    index_tip_xy:  Optional[Tuple[int, int]]
    thumb_tip_xy:  Optional[Tuple[int, int]]
    current_gesture: Gesture
    landmarks: Any  # MediaPipe landmarks
    is_pinching: bool = False  # index-thumb pinch (continuous, no debounce)

def point_in_region(x: int, y: int, region: Tuple[int, int, int, int]) -> bool:
    """Check if point (x,y) is inside region (x_min, y_min, x_max, y_max)."""
    x_min, y_min, x_max, y_max = region
    return x_min <= x <= x_max and y_min <= y <= y_max

class GestureTracker:
    def __init__(self):
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=1,
            min_detection_confidence=0.7,
            min_tracking_confidence=0.7
        )
        self.history = [] # list of center_x for WASH_OFF
        self.last_trigger_time = 0.0
        
    def process_frame(self, frame) -> GestureState:
        h, w, c = frame.shape
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.hands.process(rgb_frame)
        
        state = GestureState(
            index_tip_xy=None,
            thumb_tip_xy=None,
            current_gesture=Gesture.NONE,
            landmarks=None,
            is_pinching=False,
        )
        
        if not results.multi_hand_landmarks:
            self.history.clear()
            return state
            
        hand_landmarks = results.multi_hand_landmarks[0]
        state.landmarks = hand_landmarks
        
        # Convert landmarks to pixel coordinates
        coords = [(int(lm.x * w), int(lm.y * h)) for lm in hand_landmarks.landmark]
        state.index_tip_xy = coords[8]   # index fingertip
        state.thumb_tip_xy = coords[4]   # thumb tip

        # ── Continuous pinch detection (index tip <-> thumb tip) ────────
        # No debounce — sampled every frame for smooth picker interaction.
        pinch_dist = np.hypot(coords[8][0]-coords[4][0],
                              coords[8][1]-coords[4][1])
        ref_dist_for_pinch = np.hypot(coords[0][0]-coords[5][0],
                                      coords[0][1]-coords[5][1])
        state.is_pinching = (pinch_dist < ref_dist_for_pinch * 0.38)

        current_time = time.time()
        
        # Debounce logic for discrete events
        if current_time - self.last_trigger_time < 1.0:
            return state
            
        # Palm centroid (average of MCP joints)
        mcp_joints = [2, 5, 9, 13, 17]
        cx = sum(coords[i][0] for i in mcp_joints) / len(mcp_joints)
        cy = sum(coords[i][1] for i in mcp_joints) / len(mcp_joints)
        
        # Calculate reference distance for scaling thresholds (wrist to centroid)
        ref_dist = np.hypot(coords[0][0] - cx, coords[0][1] - cy)

        # Shared helpers for gesture detection
        def dist_to_wrist(idx):
            return np.hypot(coords[idx][0] - coords[0][0], coords[idx][1] - coords[0][1])

        def is_extended(tip_idx, pip_idx):
            """True when the fingertip is farther from the wrist than its PIP joint."""
            return dist_to_wrist(tip_idx) > dist_to_wrist(pip_idx)

        # 1. Detect FIST — all four fingertips clearly folded past PIP joints
        fist_detected = (
            dist_to_wrist(8)  < dist_to_wrist(6)  * 0.85 and
            dist_to_wrist(12) < dist_to_wrist(10) * 0.85 and
            dist_to_wrist(16) < dist_to_wrist(14) * 0.85 and
            dist_to_wrist(20) < dist_to_wrist(18) * 0.85
        )

        if fist_detected:
            state.current_gesture = Gesture.FIST
            self.last_trigger_time = current_time
            self.history.clear()
            return state

        # 1b. Detect THREE_FINGERS (index + middle + ring up, thumb + pinky folded)
        three_detected = (
            is_extended(8,  6)  and    # index up
            is_extended(12, 10) and    # middle up
            is_extended(16, 14) and    # ring up
            not is_extended(4,  3) and # thumb folded
            not is_extended(20, 18)    # pinky folded
        )
        if three_detected:
            state.current_gesture = Gesture.THREE_FINGERS
            self.last_trigger_time = current_time
            self.history.clear()
            return state

        # 2. Detect WASH_OFF — open palm with a horizontal swipe
        open_palm = (
            is_extended(4, 3) and
            is_extended(8, 6) and
            is_extended(12, 10) and
            is_extended(16, 14) and
            is_extended(20, 18)
        )
        
        if open_palm:
            self.history.append(cx)
            if len(self.history) > 8:
                self.history.pop(0)
                
            if len(self.history) == 8:
                # Check total horizontal displacement over last 8 frames
                dx = abs(self.history[-1] - self.history[0])
                if dx > w * 0.12: # threshold for swiping (WASH_OFF)
                    state.current_gesture = Gesture.WASH_OFF
                    self.last_trigger_time = current_time
                    self.history.clear()
                    return state
        else:
            self.history.clear()
            
        return state
