import cv2
import numpy as np

def get_glow_color(chemical: str) -> str:
    """Returns the hex color code for the glow of a given chemical."""
    colors = {
        'CuSO4': '#1E90FF',
        'KMnO4': '#6A0DAD',
        'K2Cr2O7': '#FF8C00',
        'FeCl3': '#FFBF00'
    }
    metals = ['Na', 'Ca', 'Zn', 'Cu', 'Mg']
    
    if chemical in colors:
        return colors[chemical]
    if chemical in metals:
        return '#C0C0C0'
        
    return '#E8E8E8' # Default colourless/white glow

class GlowRenderer:
    def __init__(self, radius=35):
        self.radius = radius
        size = radius * 2
        
        # Create an alpha mask with a radial gradient
        x = np.arange(0, size, 1, float)
        y = np.arange(0, size, 1, float)
        x, y = np.meshgrid(x - radius, y - radius)
        
        distance = np.sqrt(x**2 + y**2)
        # alpha is 1.0 at center, 0.0 at radius edge
        alpha = np.clip(1.0 - (distance / radius), 0, 1)
        
        # Apply power curve to make it look like a softer glowing light
        self.alpha_mask = np.power(alpha, 1.5)

    def draw_glow(self, frame, x, y, color_hex):
        """Draws an alpha-blended feathered glow on the frame at (x, y)."""
        color_hex = color_hex.lstrip('#')
        r = int(color_hex[0:2], 16)
        g = int(color_hex[2:4], 16)
        b = int(color_hex[4:6], 16)
        color_bgr = np.array([b, g, r], dtype=np.float32)
        
        h, w = frame.shape[:2]
        
        x1 = int(x - self.radius)
        y1 = int(y - self.radius)
        x2 = int(x + self.radius)
        y2 = int(y + self.radius)
        
        frame_x1, frame_y1 = max(0, x1), max(0, y1)
        frame_x2, frame_y2 = min(w, x2), min(h, y2)
        
        if frame_x1 >= frame_x2 or frame_y1 >= frame_y2:
            return frame
            
        mask_x1 = frame_x1 - x1
        mask_y1 = frame_y1 - y1
        mask_x2 = mask_x1 + (frame_x2 - frame_x1)
        mask_y2 = mask_y1 + (frame_y2 - frame_y1)
        
        mask = self.alpha_mask[mask_y1:mask_y2, mask_x1:mask_x2]
        mask = np.expand_dims(mask, axis=2)
        
        roi = frame[frame_y1:frame_y2, frame_x1:frame_x2].astype(np.float32)
        # Alpha blending
        blended = roi * (1 - mask) + color_bgr * mask
        
        frame[frame_y1:frame_y2, frame_x1:frame_x2] = blended.astype(np.uint8)
        return frame
