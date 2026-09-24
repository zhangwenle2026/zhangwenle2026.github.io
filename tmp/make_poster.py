from PIL import Image, ImageDraw, ImageFont
import os

# High-end poster design
# Dark navy/gold theme - premium corporate feel

W, H = 1080, 1920  # Vertical poster format

img = Image.new("RGB", (W, H), "#0d1b2a")  # Deep navy background
draw = ImageDraw.Draw(img)

# Gradient overlay (darker at top/bottom)
for y in range(H):
    alpha = int(180 * (1 - ((y - H/2) / (H/2))**2))
    r, g, b = 13, 27, 42
    nr = max(0, r - alpha//4)
    ng = max(0, g - alpha//4)
    nb = max(0, b - alpha//6)
    draw.line([(0, y), (W, y)], fill=(nr, ng, nb))

# Gold accent line at top
draw.rectangle([0, 0, W, 6], fill="#c9a84c")
draw.rectangle([0, H-6, W, H], fill="#c9a84c")

# Try to load fonts - use system fonts
font_paths = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
]

def load_font(paths, size, bold=False):
    for p in paths:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except:
                continue
    # Fallback
    return ImageFont.load_default()

font_title = load_font(font_paths, 58, bold=True)
font_subtitle = load_font(font_paths, 34)
font_date = load_font(font_paths, 42, bold=True)
font_section = load_font(font_paths, 28, bold=True)
font_body = load_font(font_paths, 22)
font_small = load_font(font_paths, 18)
font_name = load_font(font_paths, 24, bold=True)
font_role = load_font(font_paths, 16)
font_host = load_font(font_paths, 20, bold=True)

# Placeholder for Keeta logo - centered at top
logo_y = 70
# Draw logo placeholder rectangle
logo_w, logo_h = 200, 60
logo_x = (W - logo_w) // 2
draw.rounded_rectangle([logo_x, logo_y, logo_x+logo_w, logo_y+logo_h], radius=8,
                         outline="#c9a84c", width=2)
# Keeta text placeholder
draw.text((W//2, logo_y + logo_h//2), "KEETA", fill="#c9a84c", font=font_title, anchor="mm")

# Meeting Title
title_y = logo_y + logo_h + 60
draw.text((W//2, title_y), "Metropolitan Regional", fill="#c9a84c", font=font_title, anchor="mm")
draw.text((W//2, title_y + 65), "Leadership Meeting", fill="#c9a84c", font=font_title, anchor="mm")

# Decorative line under title
line_y = title_y + 130
draw.line([(W//2 - 180, line_y), (W//2 + 180, line_y)], fill="#c9a84c", width=2)

# Date
date_y = line_y + 30
draw.text((W//2, date_y), "September 11, 2026", fill="#ffffff", font=font_date, anchor="mm")
draw.text((W//2, date_y + 50), "10:00 - 12:30 BRT", fill="#a0b4c8", font=font_subtitle, anchor="mm")

# Host info
host_y = date_y + 110
draw.text((W//2, host_y), "Host: Daniel Albuquerque", fill="#c9a84c", font=font_host, anchor="mm")

# Schedule section header
schedule_y = host_y + 70
draw.text((W//2, schedule_y), "— Agenda —", fill="#c9a84c", font=font_section, anchor="mm")

# Schedule items - timeline design
items_y = schedule_y + 50
item_h = 52
gap = 14

# Color coding
colors = {
    "talk": "#1a3a5c",
    "qa": "#1e3a2e",
    "opening": "#3a2e1a",
    "cm": "#2e1a3a",
}

def draw_schedule_item(y, time, title, speaker="", section="", color_key="talk"):
    x0, x1 = 80, W - 80
    # Background
    c = colors.get(color_key, "#1a3a5c")
    draw.rounded_rectangle([x0, y, x1, y+item_h], radius=6, fill=c, outline="#c9a84c", width=1)
    
    # Time on left
    draw.text((x0 + 15, y + item_h//2), time, fill="#c9a84c", font=font_body, anchor="lm")
    
    # Title
    tx = x0 + 150
    draw.text((tx, y + item_h//2 - 10), title, fill="#ffffff", font=font_body, anchor="lm")
    if speaker:
        draw.text((tx, y + item_h//2 + 12), speaker, fill="#a0b4c8", font=font_small, anchor="lm")

# Items
ci = 0
items = [
    ("10:00", "Opening & City Best Practices", "Eric", "opening"),
    ("10:20", "Sales Process Standardization", "Tadeu Moraes (Southern)", "talk"),
    ("10:40", "Q&A Session", "", "qa"),
    ("11:00", "Sales Consultative Process", "Igor Feitosa (Western)", "talk"),
    ("11:20", "Q&A Session", "", "qa"),
    ("11:40", "Yellow Defend Process", "Renata Leite (Santos)", "talk"),
    ("12:00", "Q&A Session", "", "qa"),
    ("12:20", "Closing Remarks (CM)", "", "cm"),
]

for time, title, speaker, ck in items:
    y_pos = items_y + ci * (item_h + gap)
    draw_schedule_item(y_pos, time, title, speaker, color_key=ck)
    ci += 1

# Speakers section - photo placeholders
speakers_y = items_y + ci * (item_h + gap) + 40
draw.text((W//2, speakers_y), "— Speakers —", fill="#c9a84c", font=font_section, anchor="mm")

# 4 speaker photo placeholders in a row
photo_size = 100
photo_y = speakers_y + 40
photo_gap = (W - 160 - 4 * photo_size) // 3

speakers = [
    ("Daniel", "Albuquerque", "Host"),
    ("Tadeu", "Moraes", "Southern"),
    ("Igor", "Feitosa", "Western"),
    ("Renata", "Leite", "Santos"),
]

for i, (first, last, role) in enumerate(speakers):
    x0 = 80 + i * (photo_size + photo_gap)
    x1 = x0 + photo_size
    y1 = photo_y + photo_size
    # Circle placeholder
    draw.ellipse([x0, photo_y, x1, y1], outline="#c9a84c", width=2, fill="#1a2f4a")
    # Initials
    initials = first[0] + last[0]
    draw.text((x0 + photo_size//2, photo_y + photo_size//2), initials,
              fill="#c9a84c", font=font_name, anchor="mm")
    # Name
    name_y = y1 + 12
    draw.text((x0 + photo_size//2, name_y), f"{first} {last}",
              fill="#ffffff", font=font_small, anchor="mm")
    # Role
    draw.text((x0 + photo_size//2, name_y + 18), role,
              fill="#a0b4c8", font=font_small, anchor="mm")

# Bottom branding
brand_y = H - 80
draw.text((W//2, brand_y), "SP Metropolitan Region", fill="#a0b4c8", font=font_small, anchor="mm")

# Save
out_path = "/root/.openclaw/workspace/tmp/poster_base.png"
img.save(out_path, quality=95)
print(f"Poster saved to {out_path}")
