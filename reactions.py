import sqlite3
import cv2
import numpy as np
import time
import random

def find_reaction(chem1, chem2):
    conn = sqlite3.connect('lablens.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, reactant_1, reactant_2, conditions, products, equation, observation, block, animation_type, exam_tag
        FROM reactions 
        WHERE (reactant_1=? AND reactant_2=?) OR (reactant_1=? AND reactant_2=?)
    ''', (chem1, chem2, chem2, chem1))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        keys = ['id', 'reactant_1', 'reactant_2', 'conditions', 'products', 'equation', 'observation', 'block', 'animation_type', 'exam_tag']
        return dict(zip(keys, row))
    return None

def extract_color(text, default=(200, 200, 200)):
    obs = text.lower()
    if 'reddish-brown' in obs or 'brown' in obs:
        return (42, 42, 165) # BGR
    if 'pale blue' in obs:
        return (230, 216, 173) 
    if 'deep blue' in obs or 'blue' in obs:
        return (200, 100, 0) # BGR for deep blue
    if 'yellow' in obs:
        return (0, 255, 255)
    if 'green' in obs:
        return (0, 200, 0)
    if 'purple' in obs:
        return (130, 0, 130)
    if 'pink' in obs:
        return (203, 192, 255)
    if 'white' in obs:
        return (240, 240, 240)
    if 'colourless' in obs or 'colorless' in obs:
        return (255, 255, 255) # Transparentish white
    return default

class ReactionAnimator:
    def __init__(self):
        self.active = False
        self.reaction = None
        self.start_time = 0
        self.duration = 1.5
        self.particles = []
        
        # State to keep after animation ends
        self.final_color = None
        self.has_precipitate = False
        self.precipitate_color = None
        
        # For "no reaction" flash
        self.no_reaction_start = 0

    def trigger_no_reaction(self):
        self.no_reaction_start = time.time()

    def start_animation(self, reaction):
        self.active = True
        self.reaction = reaction
        self.start_time = time.time()
        self.particles = []
        
        # Set up final state based on animation type
        anim_type = reaction['animation_type']
        obs = reaction['observation']
        
        self.final_color = extract_color(obs, default=None)
        self.has_precipitate = False
        if anim_type == 'precipitate':
            self.has_precipitate = True
            self.precipitate_color = self.final_color
            
    def clear(self):
        self.active = False
        self.reaction = None
        self.final_color = None
        self.has_precipitate = False
        self.precipitate_color = None
        self.particles = []

    def draw(self, frame, beaker_rect, beaker_chemical=None):
        x1, y1, x2, y2 = beaker_rect
        cx = (x1 + x2) // 2
        cy = (y1 + y2) // 2
        bw = (x2 - x1) // 2
        bh = (y2 - y1) // 2
        
        current_time = time.time()
        
        # No reaction flash
        if current_time - self.no_reaction_start < 0.5:
            cv2.putText(frame, "NO REACTION", (cx - 70, cy), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            
        # Steady state drawing (after animation or while idle with contents)
        if not self.active:
            if self.reaction is not None:
                # Draw settled state of reaction
                if self.has_precipitate and self.precipitate_color:
                    cv2.ellipse(frame, (cx, y2), (bw-5, 15), 0, 0, 360, self.precipitate_color, -1)
                elif self.final_color:
                    # fill beaker liquid
                    overlay = frame.copy()
                    cv2.rectangle(overlay, (x1+5, cy), (x2-5, y2), self.final_color, -1)
                    cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)
            elif beaker_chemical:
                # Draw the single loaded chemical in the beaker
                from glow import get_glow_color
                color_hex = get_glow_color(beaker_chemical).lstrip('#')
                r, g, b = int(color_hex[0:2], 16), int(color_hex[2:4], 16), int(color_hex[4:6], 16)
                overlay = frame.copy()
                cv2.rectangle(overlay, (x1+5, cy), (x2-5, y2), (b, g, r), -1)
                cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)
                cv2.putText(frame, beaker_chemical, (cx - 30, cy + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,0,0), 1)
            return frame

        # Active Animation
        progress = (current_time - self.start_time) / self.duration
        if progress >= 1.0:
            self.active = False
            return frame
            
        anim_type = self.reaction['animation_type']
        
        if anim_type == 'gas':
            # Base liquid
            from glow import get_glow_color
            start_hex = get_glow_color(self.reaction['reactant_1']).lstrip('#')
            sr, sg, sb = int(start_hex[0:2], 16), int(start_hex[2:4], 16), int(start_hex[4:6], 16)
            overlay = frame.copy()
            cv2.rectangle(overlay, (x1+5, cy), (x2-5, y2), (sb, sg, sr), -1)
            cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)
            
            # Spawn bubbles
            if random.random() < 0.5:
                self.particles.append([random.randint(x1+10, x2-10), y2, random.uniform(3, 7), random.randint(2, 6)])
                
            new_particles = []
            for p in self.particles:
                p[1] -= p[2] # move up
                if p[1] > y1 - 50:
                    cv2.circle(frame, (int(p[0]), int(p[1])), int(p[3]), (255, 255, 255), 1)
                    new_particles.append(p)
            self.particles = new_particles
            
        elif anim_type == 'precipitate':
            # Blob grows and settles
            size = int(progress * (bw - 5))
            y_pos = int(y1 + progress * (y2 - y1))
            if self.precipitate_color:
                cv2.circle(frame, (cx, y_pos), size, self.precipitate_color, -1)
                
        elif anim_type == 'colour_change':
            from glow import get_glow_color
            start_hex = get_glow_color(self.reaction['reactant_1']).lstrip('#')
            sr, sg, sb = int(start_hex[0:2], 16), int(start_hex[2:4], 16), int(start_hex[4:6], 16)
            start_color = np.array([sb, sg, sr], dtype=np.float32)
            
            end_color = np.array(self.final_color, dtype=np.float32) if self.final_color else start_color
            
            current_color = start_color * (1 - progress) + end_color * progress
            c_bgr = (int(current_color[0]), int(current_color[1]), int(current_color[2]))
            
            overlay = frame.copy()
            cv2.rectangle(overlay, (x1+5, cy), (x2-5, y2), c_bgr, -1)
            cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)
            
        elif anim_type == 'exothermic':
            # Radiating glow
            radius = int(bh * 1.5 + np.sin(progress * 20) * 10)
            overlay = frame.copy()
            cv2.circle(overlay, (cx, cy), radius, (0, 100, 255), -1)
            cv2.addWeighted(overlay, 0.3 * (1 - progress), frame, 1.0, 0, frame)
            
        return frame
