import cv2
import sys
import time
import os
import data
import numpy as np
import mediapipe as mp
from gestures import GestureTracker, Gesture, point_in_region
from ui import UILayer
from periodic_ui import PeriodicTableUI
from glow import GlowRenderer, get_glow_color
from reactions import ReactionAnimator, find_reaction
from ai_examiner import AIExaminer

# Mild unsharp-mask — boosts edge clarity without distortion
_SHARPEN = np.array([[0,-0.4,0],[-0.4,2.6,-0.4],[0,-0.4,0]], dtype=np.float32)
def sharpen(f): return cv2.filter2D(f, -1, _SHARPEN)

def main():
    print("Initializing LabLens...")
    
    # Auto-seed database if missing
    if not os.path.exists('lablens.db'):
        print("Database not found. Seeding lablens.db...")
        data.init_db()

    cap = cv2.VideoCapture(0)
    
    if not cap.isOpened():
        print("\\nERROR: Could not open webcam.")
        print("Please ensure your webcam is connected and not being used by another application.")
        sys.exit(1)

    # Try for higher resolution
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    cap.set(cv2.CAP_PROP_FPS, 30)

    print("Webcam successfully opened. Press 'q' to quit | 'f' to toggle fullscreen.")
    fullscreen = False
    cv2.namedWindow('LabLens', cv2.WINDOW_NORMAL)
    cv2.resizeWindow('LabLens', 1280, 720)
    
    tracker = GestureTracker()
    mp_drawing = mp.solutions.drawing_utils
    mp_hands = mp.solutions.hands
    
    ui_layer = None
    pt_layer = None
    glow_renderer = GlowRenderer()
    animator = ReactionAnimator()
    ai_examiner = AIExaminer()
    
    last_event_msg = ""
    last_event_time = 0
    
    # App State
    app_mode               = 'LAB'
    loaded_chemical        = None
    previous_hovered_chem  = None
    beaker_chemical        = None
    current_reaction       = None
    reaction_done          = False
    was_in_beaker          = False
    was_over_tube          = False
    was_over_basket        = False
    was_over_equip         = {}
    hover_start_time       = 0
    prev_pinch_chem        = None    # last chem that was confirmed by pinch
    prev_pinch_equip       = None    # last equip that was confirmed by pinch
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
            
        # Mirror & sharpen
        frame = cv2.flip(frame, 1)
        frame = sharpen(frame)
        h, w, _ = frame.shape

        if ui_layer is None:
            ui_layer = UILayer(w, h)
        if pt_layer is None:
            pt_layer = PeriodicTableUI(w, h)

        # Process gesture on the clean frame BEFORE overlay
        state = tracker.process_frame(frame)
        tip_xy = state.index_tip_xy
        tx, ty = tip_xy if tip_xy else (None, None)

        if app_mode == 'PT':
            hovered_pt = None
            if tip_xy:
                for z, rect in pt_layer.cell_rects.items():
                    if point_in_region(tx, ty, rect):
                        hovered_pt = z
                        break
            
            if hovered_pt != pt_layer.hovered_element:
                hover_start_time = time.time()
                pt_layer.hovered_element = hovered_pt
                pt_layer.held_element = None
            
            if hovered_pt and (time.time() - hover_start_time > 1.5):
                pt_layer.held_element = hovered_pt
                
            if state.current_gesture == Gesture.THREE_FINGERS:
                app_mode = 'LAB'
                last_event_msg = "LAB MODE"
                last_event_time = time.time()
            
            frame = pt_layer.draw(frame)
            
            # Draw landmarks on top
            if state.landmarks:
                try:
                    mp_drawing.draw_landmarks(frame, state.landmarks, mp_hands.HAND_CONNECTIONS,
                        mp.solutions.drawing_styles.get_default_hand_landmarks_style(),
                        mp.solutions.drawing_styles.get_default_hand_connections_style())
                except:
                    mp_drawing.draw_landmarks(frame, state.landmarks, mp_hands.HAND_CONNECTIONS)
                    
            cv2.imshow('LabLens', frame)
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'): break
            elif key == ord('f'):
                fullscreen = not fullscreen
                cv2.setWindowProperty('LabLens', cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN if fullscreen else cv2.WINDOW_NORMAL)
            continue
            
        # --- LAB MODE ---
        # ── Icon hit-tests ──────────────────────────────
        over_tube = over_basket = False
        if tip_xy:
            if ui_layer.tube_icon_rect and point_in_region(tx, ty, ui_layer.tube_icon_rect):
                over_tube = True
            if ui_layer.basket_icon_rect and point_in_region(tx, ty, ui_layer.basket_icon_rect):
                over_basket = True
        if over_tube and not was_over_tube:
            ui_layer.toggle_chem_picker()
            last_event_msg = 'Reagent picker ' + ('opened' if ui_layer.chem_picker_open else 'closed')
            last_event_time = time.time()
        was_over_tube = over_tube
        if over_basket and not was_over_basket:
            ui_layer.toggle_equip_bar()
            last_event_msg = 'Equipment picker ' + ('opened' if ui_layer.equip_bar_open else 'closed')
            last_event_time = time.time()
        was_over_basket = over_basket

        # ── Equipment hover + pinch-to-select ─────────────────────
        hovered_equip = None
        pinched_equip = None
        if ui_layer.equip_bar_open and tip_xy:
            for eq_key, rect in ui_layer.equip_rects.items():
                if point_in_region(tx, ty, rect):
                    hovered_equip = eq_key
                    break
            if hovered_equip and state.is_pinching:
                pinched_equip = hovered_equip
                if pinched_equip != prev_pinch_equip:   # edge: only trigger once per pinch
                    ui_layer.active_equipment = pinched_equip
                    ui_layer.equip_bar_open   = False
                    last_event_msg = f'Equipment: {pinched_equip}'
                    last_event_time = time.time()
            prev_pinch_equip = pinched_equip if state.is_pinching else None
        
        # Block tab hit-test (only when picker open)
        if tip_xy and ui_layer.chem_picker_open:
            for blk, rect in ui_layer.block_tab_rects.items():
                if point_in_region(tx, ty, rect):
                    ui_layer.update_active_block(blk); break

        # Chemical pill hover
        hovered_chem = None
        if tip_xy and ui_layer.chem_picker_open:
            for chem, rect in ui_layer.chemical_rects.items():
                if point_in_region(tx, ty, rect):
                    hovered_chem = chem; break

        # Pinch-to-confirm chemical selection
        pinched_chem = None
        if hovered_chem and state.is_pinching:
            pinched_chem = hovered_chem
            if pinched_chem != prev_pinch_chem:   # edge: only load once per pinch gesture
                loaded_chemical = pinched_chem
                ui_layer.chem_picker_open = False
                reaction_done = False
                print(f"PINCH: Loaded {loaded_chemical}")
                last_event_msg = f"Loaded: {loaded_chemical}"
                last_event_time = time.time()
        prev_pinch_chem = pinched_chem if state.is_pinching else None

        previous_hovered_chem = hovered_chem
        
        # COMBINE Event (Beaker hit-test)
        in_beaker = False
        if state.index_tip_xy:
            x, y = state.index_tip_xy
            bx1, by1, bx2, by2 = ui_layer.beaker_rect
            pad = 20 # Add generous padding to make dropping easier
            if bx1-pad <= x <= bx2+pad and by1-pad <= y <= by2+pad:
                in_beaker = True

        if in_beaker and not was_in_beaker and loaded_chemical:
            # COMBINE!
            if beaker_chemical is None:
                beaker_chemical = loaded_chemical
                loaded_chemical = None
                print(f"Added {beaker_chemical} to beaker.")
                last_event_msg = "ADDED TO BEAKER"
                last_event_time = time.time()
            else:
                reaction = find_reaction(beaker_chemical, loaded_chemical)
                if reaction:
                    print(f"REACTION: {beaker_chemical} + {loaded_chemical}")
                    current_reaction = reaction
                    animator.start_animation(reaction)
                    beaker_chemical = None # Beaker now holds the product state (managed by animator)
                else:
                    print("No reaction.")
                    animator.trigger_no_reaction()
                loaded_chemical = None
                
        was_in_beaker = in_beaker
        
        # Handle discrete Gestures
        if state.current_gesture == Gesture.WASH_OFF:
            if loaded_chemical:
                loaded_chemical = None
                last_event_msg = "WASHED OFF"
                last_event_time = time.time()
        elif state.current_gesture == Gesture.THREE_FINGERS:
            print("THREE FINGERS: Toggle Periodic Table")
            app_mode = 'PT'
            last_event_msg = "PERIODIC TABLE MODE"
            last_event_time = time.time()
        elif state.current_gesture == Gesture.FIST:
            print("FIST: Reset beaker")
            beaker_chemical  = None
            current_reaction = None
            loaded_chemical  = None
            reaction_done    = False
            ai_examiner.current_question = None
            animator.clear()
            last_event_msg = "BEAKER RESET"
            last_event_time = time.time()

        # Mark reaction done once animation finishes
        if current_reaction and not animator.active and not reaction_done:
            reaction_done = True
                    
        # Render UI over frame
        frame = ui_layer.draw(
            frame,
            hovered_chem=hovered_chem,
            pinched_chem=pinched_chem,
            loaded_chemical=loaded_chemical,
            beaker_chemical=beaker_chemical,
            current_reaction=current_reaction,
            reaction_done=reaction_done,
            ai_question=ai_examiner.current_question,
            hovered_equip=hovered_equip,
            pinched_equip=pinched_equip,
        )
        
        # Draw Beaker Animations / Contents
        frame = animator.draw(frame, ui_layer.beaker_rect, beaker_chemical)
        
        # Draw glow on fingertip if a chemical is loaded
        if state.index_tip_xy:
            x, y = state.index_tip_xy
            if loaded_chemical:
                color_hex = get_glow_color(loaded_chemical)
                frame = glow_renderer.draw_glow(frame, x, y, color_hex)
                h_str   = color_hex.lstrip('#')
                dot_bgr = (int(h_str[4:6],16), int(h_str[2:4],16), int(h_str[0:2],16))
                # outer glow ring
                ov_ = frame.copy()
                cv2.circle(ov_, (x,y), 16, dot_bgr, 2, cv2.LINE_AA)
                cv2.addWeighted(ov_, 0.7, frame, 0.3, 0, frame)
                # solid dot
                cv2.circle(frame, (x,y),  9, dot_bgr,      -1, cv2.LINE_AA)
                cv2.circle(frame, (x,y),  9, (255,255,255),  1, cv2.LINE_AA)
                # PIL label (crisp TNR, no cv2.putText smearing)
                from ui import txt as ui_txt, FONTS as UI_FONTS
                ui_txt(frame, loaded_chemical, UI_FONTS['sm'], x+14, y-18, dot_bgr)
            else:
                # idle dot — black outline, vivid cyan fill
                cv2.circle(frame, (x,y), 11, (0,0,0),        -1, cv2.LINE_AA)
                cv2.circle(frame, (x,y),  9, (38,220,255),   -1, cv2.LINE_AA)
                cv2.circle(frame, (x,y), 11, (255,255,255),   1, cv2.LINE_AA)

        # Thumb dot + pinch line
        if state.thumb_tip_xy and state.index_tip_xy:
            tx2, ty2 = state.thumb_tip_xy
            cv2.circle(frame, (tx2,ty2), 7, (180,180,255), -1, cv2.LINE_AA)
            cv2.circle(frame, (tx2,ty2), 7, (255,255,255),  1, cv2.LINE_AA)
            if state.is_pinching:
                ix2, iy2 = state.index_tip_xy
                cv2.line(frame, (tx2,ty2), (ix2,iy2), (255,220,80), 2, cv2.LINE_AA)
                # snap ring on index
                cv2.circle(frame, (ix2,iy2), 14, (255,220,80), 2, cv2.LINE_AA)
        
        # Draw landmarks on top (styled)
        if state.landmarks:
            try:
                mp_drawing.draw_landmarks(
                    frame,
                    state.landmarks,
                    mp_hands.HAND_CONNECTIONS,
                    mp.solutions.drawing_styles.get_default_hand_landmarks_style(),
                    mp.solutions.drawing_styles.get_default_hand_connections_style(),
                )
            except Exception:
                mp_drawing.draw_landmarks(frame, state.landmarks, mp_hands.HAND_CONNECTIONS)
            
        if time.time() - last_event_time < 1.5 and last_event_msg:
            mw  = max(len(last_event_msg)*10, 160)
            mx0 = (w - mw) // 2
            my0 = 32
            ov3 = frame.copy()
            cv2.rectangle(ov3,(mx0-10,my0-8),(mx0+mw+10,my0+24),(6,10,28),-1)
            cv2.addWeighted(ov3,0.78,frame,0.22,0,frame)
            cv2.rectangle(frame,(mx0-10,my0-8),(mx0+mw+10,my0+24),(70,130,255),1)
            cv2.putText(frame, last_event_msg,(mx0,my0+13),
                        cv2.FONT_HERSHEY_SIMPLEX,0.5,(210,230,255),1,cv2.LINE_AA)
                        
        cv2.imshow('LabLens', frame)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        elif key == ord('f'):
            fullscreen = not fullscreen
            prop = cv2.WINDOW_FULLSCREEN if fullscreen else cv2.WINDOW_NORMAL
            cv2.setWindowProperty('LabLens', cv2.WND_PROP_FULLSCREEN, prop)
            if not fullscreen:
                cv2.resizeWindow('LabLens', 1280, 720)
        elif key == ord('a'):
            if current_reaction and reaction_done:
                ai_examiner.generate_question_async(current_reaction)
            
    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
