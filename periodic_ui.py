import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import sqlite3
import time

def _load_fonts():
    tnr       = ["C:/Windows/Fonts/times.ttf",   "C:/Windows/Fonts/arial.ttf",   "arial.ttf"]
    tnr_bold  = ["C:/Windows/Fonts/timesbd.ttf", "C:/Windows/Fonts/arialbd.ttf", "arialbd.ttf"]
    def _try(paths, size):
        for p in paths:
            try: return ImageFont.truetype(p, size)
            except IOError: pass
        return ImageFont.load_default()
    return {
        'xs' : _try(tnr,      11),
        'sm' : _try(tnr,      13),
        'md' : _try(tnr,      15),
        'lg' : _try(tnr_bold, 17),
        'xl' : _try(tnr_bold, 21),
        'xxl': _try(tnr_bold, 26),
    }

FONTS = _load_fonts()

PAL = {
    'bg'     : (10,  12,  22),
    'border' : (60,  90,  180),
    's'      : (60,  180, 255),   # amber in BGR
    'p'      : (80,  210, 100),   # green
    'd'      : (220, 140,  70),   # blue-ish
    'gen'    : (200,  80, 220),   # violet
    'white'  : (240, 240, 240),
    'dim'    : (110, 120, 150),
    'gold'   : (80,  200, 255),
}
BLOCK_COLOR = {'s':'s','p':'p','d':'d'}

def panel(frame, x0, y0, x1, y1, bgr, alpha=0.80):
    h = max(0, y1-y0); w = max(0, x1-x0)
    if h == 0 or w == 0: return
    sub  = frame[y0:y1, x0:x1]
    fill = np.full_like(sub, bgr, dtype=np.uint8)
    cv2.addWeighted(fill, alpha, sub, 1-alpha, 0, sub)
    frame[y0:y1, x0:x1] = sub

def border(frame, x0, y0, x1, y1, col, t=1):
    cv2.rectangle(frame, (x0, y0), (x1, y1), col, t, cv2.LINE_AA)

def txt(frame, text, font, x, y, col_bgr=(230,230,230)):
    dummy = Image.new('RGBA',(1,1))
    dd    = ImageDraw.Draw(dummy)
    bb    = dd.textbbox((0,0), text, font=font)
    tw, th = max(bb[2]-bb[0],1)+2, max(bb[3]-bb[1],1)+6
    surf  = Image.new('RGBA',(tw,th),(0,0,0,0))
    sd    = ImageDraw.Draw(surf)
    pr,pg,pb = col_bgr[2], col_bgr[1], col_bgr[0]
    sd.text((1,2), text, font=font, fill=(pr,pg,pb,255))
    arr   = np.array(surf)
    rgb_  = arr[:,:,:3][:,:,::-1]
    alph  = arr[:,:,3].astype(np.float32)/255.0
    fy0,fx0 = max(0,y), max(0,x)
    fy1   = min(frame.shape[0], fy0+th)
    fx1   = min(frame.shape[1], fx0+tw)
    sh,sw = fy1-fy0, fx1-fx0
    if sh<=0 or sw<=0: return tw
    roi   = frame[fy0:fy1,fx0:fx1].astype(np.float32)
    a_    = alph[:sh,:sw,np.newaxis]
    blnd  = roi*(1-a_) + rgb_[:sh,:sw].astype(np.float32)*a_
    frame[fy0:fy1,fx0:fx1] = blnd.astype(np.uint8)
    return tw

class PeriodicTableUI:
    def __init__(self, width, height):
        self.W = width
        self.H = height
        self.elements = self._load_elements()
        self.cell_rects = {} # atomic_number -> (x0,y0,x1,y1)
        self.hovered_element = None
        self.held_element = None

        # Calculate grid layout
        self.CELL_W = 50
        self.CELL_H = 60
        self.PAD = 4
        self.grid_x0 = (self.W - (18 * self.CELL_W)) // 2
        self.grid_y0 = (self.H - (7 * self.CELL_H)) // 2 + 30

    def _load_elements(self):
        conn = sqlite3.connect('lablens.db')
        c = conn.cursor()
        c.execute("SELECT atomic_number, symbol, name, block, period, group_num, electronic_config FROM elements")
        rows = c.fetchall()
        conn.close()
        
        elements = {}
        for row in rows:
            elements[row[0]] = {
                'atomic_number': row[0],
                'symbol': row[1],
                'name': row[2],
                'block': row[3],
                'period': row[4],
                'group': row[5],
                'config': row[6]
            }
        return elements

    def draw(self, frame):
        # Draw background
        panel(frame, 0, 0, self.W, self.H, PAL['bg'], 0.85)
        txt(frame, "PERIODIC TABLE", FONTS['xl'], 30, 20, PAL['white'])
        txt(frame, "Make a FIST to return to the Reaction Lab", FONTS['sm'], 30, 50, PAL['dim'])

        # Draw Grid
        self.cell_rects.clear()
        for z, el in self.elements.items():
            col = el['group'] - 1
            row = el['period'] - 1
            x0 = self.grid_x0 + col * self.CELL_W + self.PAD
            y0 = self.grid_y0 + row * self.CELL_H + self.PAD
            x1 = x0 + self.CELL_W - self.PAD*2
            y1 = y0 + self.CELL_H - self.PAD*2
            
            self.cell_rects[z] = (x0, y0, x1, y1)
            
            bg_col = PAL.get(BLOCK_COLOR.get(el['block'], 'gen'), PAL['white'])
            is_hovered = (self.hovered_element == z)
            
            if is_hovered:
                panel(frame, x0, y0, x1, y1, bg_col, 0.6)
                border(frame, x0, y0, x1, y1, PAL['white'], 2)
            else:
                panel(frame, x0, y0, x1, y1, bg_col, 0.2)
                border(frame, x0, y0, x1, y1, bg_col, 1)
                
            txt(frame, el['symbol'], FONTS['lg'], x0+8, y0+12, PAL['white'])
            txt(frame, str(z), FONTS['xs'], x0+4, y0+2, PAL['dim'])

        # Draw Tooltip
        if self.hovered_element and not self.held_element:
            el = self.elements[self.hovered_element]
            tx = self.W // 2 - 100
            ty = 40
            panel(frame, tx, ty, tx+200, ty+60, (20,30,50), 0.9)
            border(frame, tx, ty, tx+200, ty+60, PAL['white'], 1)
            txt(frame, f"{el['symbol']} - {el['name']}", FONTS['lg'], tx+10, ty+10, PAL['white'])
            txt(frame, f"Atomic Number: {el['atomic_number']}", FONTS['sm'], tx+10, ty+35, PAL['dim'])

        # Draw Character Card
        if self.held_element:
            el = self.elements[self.held_element]
            cx, cy = self.W // 2, self.H // 2
            cw, ch = 340, 220
            cx0, cy0 = cx - cw//2, cy - ch//2
            cx1, cy1 = cx + cw//2, cy + ch//2
            
            bg_col = PAL.get(BLOCK_COLOR.get(el['block'], 'gen'), PAL['white'])
            panel(frame, cx0, cy0, cx1, cy1, (15,20,30), 0.95)
            border(frame, cx0, cy0, cx1, cy1, bg_col, 3)
            
            # Header
            panel(frame, cx0, cy0, cx1, cy0+50, bg_col, 0.4)
            txt(frame, el['symbol'], FONTS['xxl'], cx0+20, cy0+10, PAL['white'])
            txt(frame, el['name'], FONTS['lg'], cx0+80, cy0+15, PAL['white'])
            txt(frame, str(el['atomic_number']), FONTS['lg'], cx1-40, cy0+15, PAL['white'])
            
            # Body
            y = cy0 + 70
            txt(frame, f"Block: {el['block'].upper()}", FONTS['md'], cx0+20, y, PAL['white'])
            y += 30
            txt(frame, f"Period: {el['period']}   Group: {el['group']}", FONTS['md'], cx0+20, y, PAL['white'])
            y += 30
            txt(frame, "Electronic Configuration:", FONTS['sm'], cx0+20, y, PAL['dim'])
            y += 20
            txt(frame, el['config'], FONTS['xl'], cx0+20, y, PAL['gold'])

        return frame
