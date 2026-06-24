"""
ui.py — LabLens Complete UI System
Architecture:
  - NO full-frame PIL conversion (eliminates distortion)
  - cv2.addWeighted for all panel backgrounds
  - PIL blit only for individual text strings onto named surfaces
  - State-driven popups: chem_picker, equipment_picker, reaction_panel
  - Font: Times New Roman
"""

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import sqlite3
import math
import time

# ───────────────────── FONTS ──────────────────────────
def _load_fonts():
    tnr      = ["C:/Windows/Fonts/times.ttf",   "C:/Windows/Fonts/arial.ttf"]
    tnr_bold = ["C:/Windows/Fonts/timesbd.ttf", "C:/Windows/Fonts/arialbd.ttf"]
    def _try(paths, size):
        for p in paths:
            try:
                f = ImageFont.truetype(p, size)
                return f
            except IOError:
                pass
        return ImageFont.load_default()
    return {
        'xs' : _try(tnr,      12),   # captions, labels
        'sm' : _try(tnr,      14),   # body text
        'md' : _try(tnr,      16),   # mid-weight
        'lg' : _try(tnr_bold, 17),   # section headers (bold)
        'xl' : _try(tnr_bold, 20),   # panel titles
        'xxl': _try(tnr_bold, 26),   # reaction equation / big symbol
    }

FONTS = _load_fonts()

# ───────────────────── PALETTE (BGR) ──────────────────
# Pure blue tones — no orange/amber.
PAL = {
    'bg'       : (28,  18,  12),           # very dark blue-black
    'bg2'      : (52,  36,  22),           # slightly lighter
    'border'   : (220, 130,  60),          # vivid azure border
    'border2'  : (110,  65,  28),          # subtle inner border
    's'        : (255, 210,  80),          # sky-blue   (S-block)
    'p'        : (200, 255, 120),          # cyan-green (P-block)
    'd'        : (255, 180, 100),          # steel-blue (D-block)
    'gen'      : (255, 120, 200),          # lavender   (General)
    'white'    : (255, 252, 245),          # warm white
    'dim'      : (160, 140, 110),          # slate
    'gold'     : (255, 230,  60),          # bright blue-gold
    'danger'   : (120,  60, 240),          # crimson-blue for VERY HIGH
    'cyan'     : (255, 240, 100),
    'teal'     : (220, 255, 140),
    'reaction' : (200, 255, 180),
}
BLOCK_COLOR = {'s_block':'s','p_block':'p','d_block':'d','general':'gen'}
BLOCK_ORDER = ['s_block','p_block','d_block','general']
BLOCK_LABEL = {'s_block':'S-Block','p_block':'P-Block','d_block':'D-Block','general':'General'}
BLOCK_SUB   = {'s_block':'Alkali & Alkaline Earth','p_block':'Non-metals & Metalloids',
               'd_block':'Transition Metals','general':'Compounds & Others'}

# ───────────────────── PNG ICONS ───────────────────────
import os as _os
_ICON_DIR = _os.path.dirname(_os.path.abspath(__file__))

def _load_png(filename, size):
    """Load a PNG file and resize it. Returns None if missing."""
    path = _os.path.join(_ICON_DIR, filename)
    if not _os.path.exists(path):
        return None
    img = cv2.imread(path, cv2.IMREAD_UNCHANGED)  # BGRA
    if img is None:
        return None
    return cv2.resize(img, (size, size), interpolation=cv2.INTER_AREA)

def _blit_png(frame, img, x, y, alpha=1.0):
    """Blit a BGRA image onto a BGR frame with alpha compositing."""
    if img is None:
        return
    h, w = img.shape[:2]
    # Clamp to frame bounds
    fy0, fx0 = max(0, y), max(0, x)
    fy1, fx1 = min(frame.shape[0], y+h), min(frame.shape[1], x+w)
    sy0, sx0 = fy0-y, fx0-x
    sy1, sx1 = sy0+(fy1-fy0), sx0+(fx1-fx0)
    if sy1 <= sy0 or sx1 <= sx0:
        return
    roi  = frame[fy0:fy1, fx0:fx1].astype(np.float32)
    src  = img[sy0:sy1, sx0:sx1]
    if src.shape[2] == 4:
        a = src[:,:,3:4].astype(np.float32) / 255.0 * alpha
        bgr = src[:,:,:3].astype(np.float32)
    else:
        a   = np.ones((sy1-sy0, sx1-sx0, 1), np.float32) * alpha
        bgr = src.astype(np.float32)
    blended = roi*(1-a) + bgr*a
    frame[fy0:fy1, fx0:fx1] = blended.astype(np.uint8)

EQUIPMENT = [
    {'key':'beaker',   'label':'Beaker'},
    {'key':'testtube', 'label':'Test Tube'},
    {'key':'flask',    'label':'Conical Flask'},
]

# ───────────────────── DATA ───────────────────────────
def get_chemicals_by_block():
    conn = sqlite3.connect('lablens.db')
    c = conn.cursor()
    c.execute("SELECT reactant_1, reactant_2, block FROM reactions")
    rows = c.fetchall(); conn.close()
    blks = {k: set() for k in BLOCK_ORDER}
    for r1, r2, blk in rows:
        if blk in blks:
            blks[blk].add(r1); blks[blk].add(r2)
    return {k: sorted(blks[k]) for k in BLOCK_ORDER}

# ───────────────────── DRAW HELPERS ───────────────────
def panel(frame, x0, y0, x1, y1, bgr=None, alpha=0.80):
    """Blend a solid-colour rectangle over the frame. No frame copy distortion."""
    if bgr is None: bgr = PAL['bg']
    h = max(0, y1-y0); w = max(0, x1-x0)
    if h == 0 or w == 0: return
    sub  = frame[y0:y1, x0:x1]
    fill = np.full_like(sub, bgr, dtype=np.uint8)
    cv2.addWeighted(fill, alpha, sub, 1-alpha, 0, sub)
    frame[y0:y1, x0:x1] = sub

def border(frame, x0, y0, x1, y1, col=None, t=1):
    if col is None: col = PAL['border']
    cv2.rectangle(frame, (x0, y0), (x1, y1), col, t, cv2.LINE_AA)

def txt(frame, text, font, x, y, col_bgr=(230,230,230)):
    """Blit a single line of PIL-rendered (anti-aliased) text onto the frame."""
    dummy = Image.new('RGBA',(1,1))
    dd    = ImageDraw.Draw(dummy)
    bb    = dd.textbbox((0,0), text, font=font)
    tw, th = max(bb[2]-bb[0],1)+2, max(bb[3]-bb[1],1)+6
    surf  = Image.new('RGBA',(tw,th),(0,0,0,0))
    sd    = ImageDraw.Draw(surf)
    # PIL takes RGB, not BGR
    pr,pg,pb = col_bgr[2], col_bgr[1], col_bgr[0]
    sd.text((1,2), text, font=font, fill=(pr,pg,pb,255))
    arr   = np.array(surf)
    rgb_  = arr[:,:,:3][:,:,::-1]    # convert to BGR
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
    return tw   # return width so caller can chain

def txt_center(frame, text, font, cx, y, col_bgr=(230,230,230)):
    dummy = Image.new('RGBA',(1,1))
    dd    = ImageDraw.Draw(dummy)
    bb    = dd.textbbox((0,0), text, font=font)
    tw    = bb[2]-bb[0]
    txt(frame, text, font, cx - tw//2, y, col_bgr)

def wrap_txt(frame, text, font, x, y, max_w, col_bgr, line_h=18, bg_bgr=None):
    words  = text.split()
    line   = ""
    lines  = []
    dummy  = Image.new('RGBA',(1,1))
    dd     = ImageDraw.Draw(dummy)
    for w_ in words:
        test = (line+" "+w_).strip()
        bb   = dd.textbbox((0,0), test, font=font)
        if bb[2]-bb[0] > max_w and line:
            lines.append(line); line=w_
        else:
            line=test
    if line: lines.append(line)
    if bg_bgr:
        total_h = len(lines)*line_h+8
        panel(frame, x-4, y-4, x+max_w+4, y+total_h, bg_bgr, 0.55)
    for ln in lines:
        txt(frame, ln, font, x, y, col_bgr); y+=line_h
    return y

# ───────────────────── ICON DRAWING ───────────────────
def draw_tube_icon(frame, x, y, s=38, hovered=False):
    """Draw a test-tube icon at top-left."""
    col   = PAL['gold'] if hovered else PAL['dim']
    # Body
    pts   = np.array([[x+s//3,y+2],[x+s//3,y+s-10],[x+s//2,y+s],[x+2*s//3,y+s-10],[x+2*s//3,y+2]], np.int32)
    ovl   = frame.copy()
    cv2.fillPoly(ovl, [pts], (col[0]//4, col[1]//4, col[2]//4))
    cv2.addWeighted(ovl, 0.55, frame, 0.45, 0, frame)
    cv2.polylines(frame, [pts], False, col, 2, cv2.LINE_AA)
    # Liquid
    liq_pts = np.array([[x+s//3+2,y+s-24],[x+s//3+2,y+s-12],[x+s//2,y+s-2],[x+2*s//3-2,y+s-12],[x+2*s//3-2,y+s-24]], np.int32)
    cv2.fillPoly(frame, [liq_pts], (100,200,255))
    # Cap
    cv2.line(frame,(x+s//3-4,y+2),(x+2*s//3+4,y+2), col, 3, cv2.LINE_AA)
    if hovered:
        cv2.circle(frame,(x+s//2,y+s//2),s//2+4,col,1,cv2.LINE_AA)

def draw_basket_icon(frame, x, y, s=38, hovered=False):
    """Draw a basket/flask icon at bottom-right."""
    col = PAL['gold'] if hovered else PAL['dim']
    cx,cy_ = x+s//2, y+s//2
    # Flask body (round bottom)
    cv2.circle(frame,(cx,cy_+8),s//3,( col[0]//4,col[1]//4,col[2]//4),-1)
    cv2.circle(frame,(cx,cy_+8),s//3,col,2,cv2.LINE_AA)
    # Neck
    cv2.rectangle(frame,(cx-5,y+4),(cx+5,cy_+2),(col[0]//4,col[1]//4,col[2]//4),-1)
    cv2.rectangle(frame,(cx-5,y+4),(cx+5,cy_+2),col,2,cv2.LINE_AA)
    # Shoulders
    cv2.line(frame,(cx-5,cy_+2),(cx-s//3,cy_+8),col,2,cv2.LINE_AA)
    cv2.line(frame,(cx+5,cy_+2),(cx+s//3,cy_+8),col,2,cv2.LINE_AA)
    # Cap
    cv2.line(frame,(cx-7,y+4),(cx+7,y+4),col,3,cv2.LINE_AA)
    if hovered:
        cv2.circle(frame,(cx,cy_+4),s//2+4,col,1,cv2.LINE_AA)

# ───────────────────── EQUIPMENT ICONS ────────────────
def draw_equipment_icon_cv(frame, key, cx, cy, size=36, selected=False):
    col = PAL['gold'] if selected else (160,170,190)
    if key == 'beaker':
        bw, bh = size//2, size*3//4
        pts = np.array([[cx-bw,cy-bh],[cx-bw+3,cy+bh],[cx+bw-3,cy+bh],[cx+bw,cy-bh]],np.int32)
        cv2.polylines(frame,[pts],False,col,2,cv2.LINE_AA)
        cv2.line(frame,(cx-bw-4,cy-bh),(cx+bw+4,cy-bh),col,2,cv2.LINE_AA)
        cv2.line(frame,(cx-bw-4,cy-bh),(cx-bw-2,cy-bh-6),col,2,cv2.LINE_AA)
    elif key == 'testtube':
        cv2.line(frame,(cx,cy-size//2),(cx,cy+size//3),col,6,cv2.LINE_AA)
        cv2.circle(frame,(cx,cy+size//3),5,col,-1)
        cv2.line(frame,(cx-7,cy-size//2),(cx+7,cy-size//2),col,3,cv2.LINE_AA)
    elif key == 'flask':
        cv2.circle(frame,(cx,cy+size//4),size//3,col,2,cv2.LINE_AA)
        cv2.rectangle(frame,(cx-4,cy-size//2),(cx+4,cy+size//4-size//3),(col[0]//2,col[1]//2,col[2]//2),-1)
        cv2.rectangle(frame,(cx-4,cy-size//2),(cx+4,cy+size//4-size//3),col,2,cv2.LINE_AA)
        cv2.line(frame,(cx-6,cy-size//2),(cx+6,cy-size//2),col,3,cv2.LINE_AA)
        cv2.line(frame,(cx-4,cy+size//4-size//3),(cx-size//3,cy+size//4),col,2,cv2.LINE_AA)
        cv2.line(frame,(cx+4,cy+size//4-size//3),(cx+size//3,cy+size//4),col,2,cv2.LINE_AA)

# ───────────────────── MAIN UI LAYER ──────────────────
class UILayer:
    ICON_SZ       = 44
    ICON_PAD      = 10
    INFO_W        = 220   # right panel — narrower to give more camera space
    PILL_H        = 28
    PILL_GAP      = 6
    BLOCK_TAB_W   = 92
    BLOCK_TAB_H   = 30
    PICKER_H      = 310
    EQUIP_BAR_H   = 90

    def __init__(self, width, height):
        self.W = width; self.H = height
        self.chems_by_block    = get_chemicals_by_block()
        self.chemical_rects    = {}
        self.block_tab_rects   = {}
        self.equip_rects       = {}
        self.tube_icon_rect    = None
        self.basket_icon_rect  = None

        # Load PNG icons (resize to small icon size)
        self.img_chem = _load_png('chem.png', self.ICON_SZ)       # test tube icon
        self.img_cone = None

        # Picker overlay (centre, just below top icon strip)
        pw = min(580, width - 40)
        ph = self.PICKER_H
        self.picker_rect = ((width-pw)//2, 58, (width+pw)//2, 58+ph)

        # Beaker (conical flask) — bottom-centre of camera zone
        info_x   = width - self.INFO_W
        cam_cx   = info_x // 2                        # centre of camera zone
        pot_h    = 80
        pot_w    = 110
        bx = cam_cx
        by = height - 10                              # bottom edge
        self.beaker_cx = bx; self.beaker_cy = by
        self.BW = pot_w // 2; self.BH = pot_h
        # hit rect = the flask body area (generous for finger drop)
        self.beaker_rect = (bx - self.BW, by - self.BH, bx + self.BW, by)

        # Active state
        self.active_block     = 's_block'
        self.active_equipment = 'beaker'
        self.chem_picker_open = False
        self.equip_bar_open   = False

    # ── update_active_block ─────────────────────────
    def update_active_block(self, blk):
        if blk in BLOCK_ORDER:
            self.active_block = blk

    # ── toggle functions ────────────────────────────
    def toggle_chem_picker(self):
        self.chem_picker_open = not self.chem_picker_open
        if self.chem_picker_open:
            self.equip_bar_open = False

    def toggle_equip_bar(self):
        self.equip_bar_open = not self.equip_bar_open
        if self.equip_bar_open:
            self.chem_picker_open = False

    # ── Main draw ───────────────────────────────────
    def draw(self, frame, hovered_chem=None, pinched_chem=None, loaded_chemical=None,
             beaker_chemical=None, current_reaction=None, reaction_done=False,
             ai_question=None, hovered_equip=None, pinched_equip=None):

        t = time.time()
        W, H = self.W, self.H

        # Right info panel (always visible, but thinner)
        ix = W - self.INFO_W
        self._draw_info_panel(frame, ix, loaded_chemical,
                              beaker_chemical, current_reaction, reaction_done, ai_question)

        # Tiny permanent header strip
        self._draw_header(frame, ix)

        # Draw beaker
        self._draw_beaker_zone(frame, beaker_chemical, loaded_chemical, t)

        # Chem picker popup
        if self.chem_picker_open:
            self._draw_chem_picker(frame, hovered_chem, pinched_chem)

        # Equipment bar popup
        if self.equip_bar_open:
            self._draw_equip_bar(frame, hovered_equip, pinched_equip)

        # Top-left reagent icon — use chem.png if available, else fallback
        ti = self.ICON_PAD
        self.tube_icon_rect = (ti, ti, ti+self.ICON_SZ, ti+self.ICON_SZ)
        if self.img_chem is not None:
            alpha_v = 1.0 if self.chem_picker_open else 0.65
            _blit_png(frame, self.img_chem, ti, ti, alpha=alpha_v)
            if self.chem_picker_open:
                cv2.rectangle(frame, (ti-2,ti-2), (ti+self.ICON_SZ+2,ti+self.ICON_SZ+2),
                              PAL['gold'], 2, cv2.LINE_AA)
        else:
            draw_tube_icon(frame, ti, ti, self.ICON_SZ, hovered=self.chem_picker_open)

        # Bottom-right basket icon (equipment)
        bix = W - self.ICON_SZ - self.ICON_PAD
        biy = H - self.ICON_SZ - self.ICON_PAD
        self.basket_icon_rect = (bix, biy, bix+self.ICON_SZ, biy+self.ICON_SZ)
        draw_basket_icon(frame, bix, biy, self.ICON_SZ, hovered=self.equip_bar_open)

        # Mode hint — bottom of camera zone, above the flask
        hint = "3-fingers = PT Mode  |  Wave = Unload  |  Pinch = Select"
        txt_center(frame, hint, FONTS['xs'], ix//2, H - self.BH - 45, PAL['dim'])

        return frame

    # ── Beaker zone (vector drawn at bottom-centre) ─────
    def _draw_beaker_zone(self, frame, beaker_chemical, loaded_chemical, t):
        from glow import get_glow_color

        cx, cy = self.beaker_cx, self.beaker_cy
        bw, bh = self.BW, self.BH
        top_y = cy - bh; bot_y = cy

        # Liquid
        liq = None; lbl = ""
        if beaker_chemical:
            hx = get_glow_color(beaker_chemical).lstrip('#')
            r,g,b = int(hx[0:2],16),int(hx[2:4],16),int(hx[4:6],16)
            liq = (b,g,r); lbl = beaker_chemical

        # Draw beaker body
        lx = cx-bw; rx = cx+bw
        pts = np.array([[lx,top_y],[lx+3,bot_y],[rx-3,bot_y],[rx,top_y]],np.int32)

        if liq:
            liq_top = int(bot_y - bh*0.6)
            lpts = np.array([[lx+4,liq_top],[lx+4,bot_y-2],[rx-4,bot_y-2],[rx-4,liq_top]],np.int32)
            ov = frame.copy()
            cv2.fillPoly(ov,[lpts],liq)
            cv2.addWeighted(ov,0.6,frame,0.4,0,frame)
            sr,sg,sb = min(liq[0]+50,255),min(liq[1]+50,255),min(liq[2]+50,255)
            cv2.line(frame,(lx+5,liq_top+2),(rx-5,liq_top+2),(sr,sg,sb),1)

        col = PAL['border']
        cv2.polylines(frame,[pts],False,col,2,cv2.LINE_AA)
        cv2.line(frame,(lx+3,bot_y),(rx-3,bot_y),col,2,cv2.LINE_AA)
        cv2.line(frame,(lx-4,top_y),(rx+4,top_y),col,2,cv2.LINE_AA)
        cv2.line(frame,(lx-4,top_y),(lx-2,top_y-6),col,2,cv2.LINE_AA)
        for i in range(1,4):
            gy = int(bot_y - bh*i*0.25)
            cv2.line(frame,(rx-10,gy),(rx-2,gy),(50,90,160),1)

        if lbl:
            txt_center(frame, lbl, FONTS['xs'], cx, bot_y+8, PAL['dim'])

        # Pulsing ring when loaded
        if loaded_chemical:
            pulse = 0.45 + 0.55*math.sin(t*5)
            ov2 = frame.copy()
            cy_mid = cy - bh//2
            cv2.circle(ov2,(cx,cy_mid),bw+18,(60,200,255),2,cv2.LINE_AA)
            cv2.addWeighted(ov2,pulse*0.6,frame,1-pulse*0.6,0,frame)
            txt_center(frame,"DROP HERE",FONTS['xs'],cx,top_y-14,(80,210,255))

    # ── Chemical picker popup ────────────────────────
    def _draw_chem_picker(self, frame, hovered_chem, pinched_chem=None):
        px0, py0, px1, py1 = self.picker_rect
        pw = px1 - px0
        tab_w = self.BLOCK_TAB_W

        # Background — rich dark navy
        panel(frame, px0, py0, px1, py1, PAL['bg2'], 0.95)
        border(frame, px0, py0, px1, py1, PAL['border'], 2)

        # Title bar
        panel(frame, px0, py0, px1, py0+26, PAL['bg'], 0.97)
        txt(frame, "REAGENT SELECTOR  —  pinch to load a chemical",
            FONTS['xs'], px0+8, py0+6, PAL['dim'])

        # Close hint
        cv2.putText(frame, 'X', (px1-20, py0+19),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, PAL['dim'], 1, cv2.LINE_AA)

        # Block tabs (left column)
        self.block_tab_rects.clear()
        for i, blk in enumerate(BLOCK_ORDER):
            ty0 = py0 + 30 + i*(self.BLOCK_TAB_H + 5)
            ty1 = ty0 + self.BLOCK_TAB_H
            tx0, tx1 = px0+4, px0+tab_w-4
            self.block_tab_rects[blk] = (tx0, ty0, tx1, ty1)
            is_act = (blk == self.active_block)
            col    = PAL[BLOCK_COLOR[blk]]
            if is_act:
                panel(frame, tx0, ty0, tx1, ty1, col, 0.28)
                border(frame, tx0, ty0, tx1, ty1, col, 2)
                # vivid left accent bar
                cv2.rectangle(frame, (tx0, ty0), (tx0+3, ty1), col, -1)
            else:
                panel(frame, tx0, ty0, tx1, ty1, (20,24,46), 0.85)
                border(frame, tx0, ty0, tx1, ty1, PAL['border2'], 1)
            col_txt = col if is_act else PAL['dim']
            txt(frame, BLOCK_LABEL[blk], FONTS['sm'], tx0+10, ty0+6, col_txt)

        # Chemicals for active block (right area — flow layout)
        self.chemical_rects.clear()
        chems   = self.chems_by_block.get(self.active_block, [])
        col     = PAL[BLOCK_COLOR[self.active_block]]
        rx0     = px0 + tab_w + 10
        ry_base = py0 + 34
        x_cur   = rx0
        y_cur   = ry_base

        for chem in chems:
            cw = max(len(chem)*9 + 18, 56)
            if x_cur + cw > px1 - 8:
                x_cur = rx0; y_cur += self.PILL_H + self.PILL_GAP
            px_0 = x_cur; px_1 = x_cur + cw
            py_0 = y_cur; py_1 = y_cur + self.PILL_H - 2
            rect = (px_0, py_0, px_1, py_1)
            self.chemical_rects[chem] = rect
            is_pinched = (chem == pinched_chem)
            is_hov     = (chem == hovered_chem)
            if is_pinched:
                # bright solid fill — confirmed selection
                panel(frame, px_0, py_0, px_1, py_1, col, 0.70)
                border(frame, px_0, py_0, px_1, py_1, PAL['white'], 2)
                txt_col = PAL['white']
            elif is_hov:
                # lighter fill — just hovering
                panel(frame, px_0, py_0, px_1, py_1, col, 0.32)
                border(frame, px_0, py_0, px_1, py_1, col, 1)
                txt_col = PAL['white']
            else:
                panel(frame, px_0, py_0, px_1, py_1, (20,24,46), 0.78)
                border(frame, px_0, py_0, px_1, py_1, PAL['border2'], 1)
                txt_col = col
            txt(frame, chem, FONTS['sm'], px_0+7, py_0+5, txt_col)
            x_cur += cw + self.PILL_GAP

        # Block subtitle
        sub = BLOCK_SUB.get(self.active_block,'')
        txt(frame, sub, FONTS['xs'], px0+4, py1-18, PAL['dim'])

    # ── Equipment bar popup ──────────────────────────
    def _draw_equip_bar(self, frame, hovered_equip=None, pinched_equip=None):
        W, H = self.W, self.H
        ix   = W - self.INFO_W
        bh   = self.EQUIP_BAR_H
        ey0  = H - bh - self.ICON_SZ - self.ICON_PAD*2
        ey1  = H - self.ICON_SZ - self.ICON_PAD*2

        panel(frame, 0, ey0, ix, ey1, PAL['bg2'], 0.93)
        border(frame, 0, ey0, ix, ey1, PAL['border'], 2)
        txt(frame, "EQUIPMENT  —  pinch to select", FONTS['xs'], 10, ey0+5, PAL['dim'])

        n      = len(EQUIPMENT)
        slot_w = ix // n
        self.equip_rects.clear()

        for i, eq in enumerate(EQUIPMENT):
            sx0 = i*slot_w; sx1 = sx0+slot_w
            scx = (sx0+sx1)//2; scy = ey0+18+(bh-28)//2
            is_sel     = (eq['key'] == self.active_equipment)
            is_pinched = (eq['key'] == pinched_equip)
            is_hov     = (eq['key'] == hovered_equip)
            if is_pinched or is_sel:
                panel(frame, sx0+4, ey0+16, sx1-4, ey1-4, PAL['gold'], 0.22)
                border(frame, sx0+4, ey0+16, sx1-4, ey1-4, PAL['gold'], 2)
            elif is_hov:
                panel(frame, sx0+4, ey0+16, sx1-4, ey1-4, PAL['border2'], 0.55)
                border(frame, sx0+4, ey0+16, sx1-4, ey1-4, PAL['border'], 1)
            self.equip_rects[eq['key']] = (sx0+4, ey0+16, sx1-4, ey1-4)
            draw_equipment_icon_cv(frame, eq['key'], scx, scy, 32, is_sel or is_pinched)
            txt_center(frame, eq['label'], FONTS['xs'], scx, ey1-16,
                       PAL['gold'] if (is_sel or is_pinched) else PAL['dim'])
            if i > 0:
                cv2.line(frame, (sx0, ey0+20), (sx0, ey1-6), PAL['border2'], 1)

    # ── Right info panel ─────────────────────────────
    def _draw_info_panel(self, frame, ix, loaded_chemical,
                         beaker_chemical, current_reaction, reaction_done, ai_question=None):
        W, H = self.W, self.H
        panel(frame, ix, 0, W, H, PAL['bg2'], 0.90)
        cv2.line(frame, (ix,0), (ix,H), PAL['border'], 2, cv2.LINE_AA)

        # Header
        panel(frame, ix, 0, W, 36, (24,28,58), 0.97)
        txt(frame, "INFO", FONTS['xl'], ix+10, 8, PAL['white'])
        cv2.line(frame, (ix+6,36), (W-6,36), PAL['border2'], 1)

        y = 44
        panel_w = W - ix - 14   # usable text width inside the panel

        if current_reaction and reaction_done:
            r    = current_reaction
            eq   = r.get('equation','')
            obs  = r.get('observation','')
            cond = r.get('conditions','')
            tag  = r.get('exam_tag','')
            blk  = r.get('block','')

            if y < H-20:
                txt(frame, "Equation", FONTS['lg'], ix+8, y, PAL['gold']); y += 18
            if y < H-20:
                y = wrap_txt(frame, eq, FONTS['xs'], ix+8, y, panel_w,
                             (200,230,255), 14, bg_bgr=(16,28,52)); y += 6

            if cond and cond.lower() != 'none' and y < H-20:
                txt(frame, "Conditions", FONTS['lg'], ix+8, y, (120,200,255)); y += 18
                y = wrap_txt(frame, cond, FONTS['xs'], ix+8, y, panel_w,
                             (240,222,160), 14, bg_bgr=(40,28,12)); y += 6

            if y < H-20:
                txt(frame, "Observation", FONTS['lg'], ix+8, y, (100,220,130)); y += 18
            if y < H-20:
                y = wrap_txt(frame, obs, FONTS['xs'], ix+8, y, panel_w,
                             (160,245,175), 14, bg_bgr=(10,30,15)); y += 6

            if y < H-30:
                tc  = {'VERY HIGH': PAL['danger'],
                       'HIGH':      (60, 160, 255),
                       'MODERATE':  (60, 200,  80)}.get(tag, PAL['dim'])
                lbl = f"JEE: {tag}"          # shortened to fit
                tw2 = min(panel_w - 4, max(len(lbl)*7+24, 60))
                panel(frame, ix+8, y, ix+8+tw2, y+20, (20,20,36), 0.80)
                border(frame, ix+8, y, ix+8+tw2, y+20, PAL['border2'], 1)
                cv2.circle(frame, (ix+17, y+10), 4, tc, -1, cv2.LINE_AA)
                txt(frame, lbl, FONTS['xs'], ix+26, y+3, (tc[2],tc[1],tc[0])); y += 26

            if y < H-20:
                blk_lbl = blk.replace('_','-').upper()
                txt(frame, f"Block: {blk_lbl}", FONTS['xs'], ix+8, y, PAL['dim']); y += 20

            if ai_question and y < H-20:
                cv2.line(frame, (ix+6,y), (W-6,y), PAL['border2'], 1); y += 5
                txt(frame, "AI Examiner", FONTS['lg'], ix+8, y, (230,150,255)); y += 18
                y = wrap_txt(frame, ai_question, FONTS['sm'], ix+8, y, panel_w,
                             (255,220,255), 15, bg_bgr=(40,14,40)); y += 4
            elif not ai_question and y < H-18:
                txt(frame, "[a] AI question", FONTS['xs'], ix+8, y, PAL['dim'])

        elif beaker_chemical:
            txt(frame, "In Beaker", FONTS['lg'], ix+8, y, PAL['gold']); y += 22
            panel(frame, ix+6, y, W-6, y+32, (18,44,72), 0.68)
            txt(frame, beaker_chemical, FONTS['xl'], ix+14, y+6, (210,240,255)); y += 40
            txt(frame, "Hover & pinch a 2nd reagent", FONTS['xs'], ix+8, y, PAL['dim']); y += 16
            txt(frame, "then move into beaker.", FONTS['xs'], ix+8, y, PAL['dim'])

        elif loaded_chemical:
            txt(frame, "Loaded", FONTS['lg'], ix+8, y, (80,220,110)); y += 22
            panel(frame, ix+6, y, W-6, y+32, (12,42,20), 0.68)
            txt(frame, loaded_chemical, FONTS['xl'], ix+14, y+6, (180,255,190)); y += 40
            txt(frame, "Move to beaker to drop.", FONTS['xs'], ix+8, y, PAL['dim']); y += 16
            txt(frame, "Pinch another to swap.", FONTS['xs'], ix+8, y, PAL['dim'])

        else:
            txt(frame, "How to Use", FONTS['lg'], ix+8, y, (170,150,255)); y += 24
            y = wrap_txt(frame,
                "Dip a finger into a chemical, then combine it with another in the beaker.",
                FONTS['sm'], ix+8, y, W-ix-16, PAL['dim'], 18)

    # ── Header strip ─────────────────────────────────
    def _draw_header(self, frame, info_x):
        panel(frame, 0, 0, info_x, 28, PAL['bg2'], 0.82)
        cv2.line(frame, (0,28), (info_x,28), PAL['border2'], 1)
        mid = info_x // 2
        txt_center(frame, "LabLens  |  Gesture Chemistry Lab",
                   FONTS['xs'], mid, 7, (140, 160, 220))
