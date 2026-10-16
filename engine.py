"""מנוע הרינדור של Magnetoti - ללא תלות בממשק גרפי."""
import math
from dataclasses import dataclass, field
from PIL import Image, ImageDraw, ImageOps, ImageEnhance, ImageFilter

MM_PER_INCH = 25.4

PAPER_SIZES_MM = {
    "A4 (21×29.7 ס״מ)": (210, 297),
    "Letter (21.6×27.9 ס״מ)": (215.9, 279.4),
    "A3 (29.7×42 ס״מ)": (297, 420),
    "A5 (14.8×21 ס״מ)": (148, 210),
    "תמונה 10×15 ס״מ": (100, 150),
    "תמונה 13×18 ס״מ": (130, 180),
}

MAGNET_PRESETS_CM = {
    "5×5": (5.0, 5.0),
    "5×7.5": (5.0, 7.5),
    "6×6": (6.0, 6.0),
    "6×9": (6.0, 9.0),
    "7.5×10": (7.5, 10.0),
    "7.5×7.5": (7.5, 7.5),
    "9×13": (9.0, 13.0),
    "מותאם אישית": None,
}

FRAMES = ["ללא מסגרת", "מסגרת רוחב", "מסגרת אורך", "פולארויד"]
EFFECTS = ["ללא", "שחור לבן", "ספיה", "חד", "בהיר", "ניגודיות", "וינטג'"]

QUALITY_DPI = {"טיוטה — 150 DPI": 150, "רגיל — 300 DPI": 300, "גבוה — 450 DPI": 450, "Ultra — 600 DPI": 600}


def mm_to_px(mm, dpi):
    return int(round(mm / MM_PER_INCH * dpi))


@dataclass
class Settings:
    paper_mm: tuple = (210, 297)
    landscape: bool = False
    magnet_mm: tuple = (75, 100)
    auto_rotate: bool = False      # סיבוב המגנט כדי להכניס יותר על הדף
    margin_mm: tuple = (5, 5, 5, 5)  # top, right, bottom, left
    gap_mm: float = 2.0
    frame: str = "ללא מסגרת"
    frame_mm: float = 3.0
    rounded: bool = False
    corner_mm: float = 3.0
    effect: str = "ללא"
    gamma: float = 1.0
    cut_lines: bool = True
    fit_mode: str = "fill"          # fill = חיתוך למילוי, fit = התאמה מלאה
    dpi: int = 300


@dataclass
class Item:
    path: str
    copies: int = 1
    _img: Image.Image = field(default=None, repr=False)

    def image(self):
        if self._img is None:
            im = Image.open(self.path)
            im = ImageOps.exif_transpose(im).convert("RGB")
            im.thumbnail((4000, 4000))
            self._img = im
        return self._img


def grid_for(s: Settings):
    """מחזיר (עמודות, שורות, מגנט_רוחב_מ״מ, מגנט_גובה_מ״מ, סובב?)"""
    pw, ph = s.paper_mm
    if s.landscape:
        pw, ph = ph, pw
    t, r, b, l = s.margin_mm
    aw, ah = pw - l - r, ph - t - b
    best = None
    variants = [(s.magnet_mm[0], s.magnet_mm[1], False)]
    if s.auto_rotate and s.magnet_mm[0] != s.magnet_mm[1]:
        variants.append((s.magnet_mm[1], s.magnet_mm[0], True))
    for mw, mh, rot in variants:
        cols = int((aw + s.gap_mm) // (mw + s.gap_mm)) if mw <= aw else 0
        rows = int((ah + s.gap_mm) // (mh + s.gap_mm)) if mh <= ah else 0
        if best is None or cols * rows > best[0] * best[1]:
            best = (cols, rows, mw, mh, rot)
    return best


def apply_effect(im: Image.Image, effect: str, gamma: float):
    if effect == "שחור לבן":
        im = ImageOps.grayscale(im).convert("RGB")
    elif effect == "ספיה":
        g = ImageOps.grayscale(im)
        im = ImageOps.colorize(g, "#2b1a08", "#f5deb3", mid="#a67c52")
    elif effect == "חד":
        im = im.filter(ImageFilter.UnsharpMask(radius=2, percent=160, threshold=2))
    elif effect == "בהיר":
        im = ImageEnhance.Brightness(im).enhance(1.2)
    elif effect == "ניגודיות":
        im = ImageEnhance.Contrast(im).enhance(1.3)
        im = ImageEnhance.Color(im).enhance(1.15)
    elif effect == "וינטג'":
        im = ImageEnhance.Color(im).enhance(0.7)
        im = ImageEnhance.Contrast(im).enhance(0.9)
        overlay = Image.new("RGB", im.size, (255, 225, 170))
        im = Image.blend(im, overlay, 0.18)
    if abs(gamma - 1.0) > 0.01:
        inv = 1.0 / max(gamma, 0.05)
        lut = [int(round(255 * ((i / 255) ** inv))) for i in range(256)]
        im = im.point(lut * 3)
    return im


def render_magnet(src: Image.Image, w_px: int, h_px: int, s: Settings, rotated: bool) -> Image.Image:
    """מצייר מגנט בודד בגודל המבוקש."""
    w_px, h_px = max(w_px, 4), max(h_px, 4)
    frame = s.frame
    fpx = mm_to_px(s.frame_mm, s.dpi)

    # מסגרת
    if frame == "ללא מסגרת":
        box = (0, 0, w_px, h_px)
    elif frame == "מסגרת רוחב":
        box = (fpx, fpx, w_px - fpx, h_px - fpx)
    elif frame == "מסגרת אורך":
        box = (fpx, 0, w_px - fpx, h_px)
    else:  # פולארויד
        side = int(w_px * 0.07)
        top = int(w_px * 0.07)
        bottom = int(h_px * 0.2)
        box = (side, top, w_px - side, h_px - bottom)

    bw, bh = max(box[2] - box[0], 2), max(box[3] - box[1], 2)
    photo = src
    # אם המגנט מסובב והתמונה לאורך/לרוחב לא מתאימה — מסובבים את התמונה
    if rotated:
        photo = photo.rotate(90, expand=True)

    if s.fit_mode == "fill":
        photo = ImageOps.fit(photo, (bw, bh), Image.LANCZOS)
    else:
        photo = ImageOps.contain(photo, (bw, bh), Image.LANCZOS)
        bg = Image.new("RGB", (bw, bh), "white")
        bg.paste(photo, ((bw - photo.width) // 2, (bh - photo.height) // 2))
        photo = bg

    photo = apply_effect(photo, s.effect, s.gamma)
    canvas = Image.new("RGB", (w_px, h_px), "white")
    canvas.paste(photo, (box[0], box[1]))

    if s.rounded:
        r = mm_to_px(s.corner_mm, s.dpi)
        mask = Image.new("L", (w_px * 2, h_px * 2), 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, w_px * 2 - 1, h_px * 2 - 1), r * 2, fill=255)
        mask = mask.resize((w_px, h_px), Image.LANCZOS)
        out = Image.new("RGB", (w_px, h_px), "white")
        out.paste(canvas, (0, 0), mask)
        canvas = out
    return canvas


def expand_items(items):
    out = []
    for it in items:
        out.extend([it] * max(1, it.copies))
    return out


def page_count(items, s: Settings):
    cols, rows, *_ = grid_for(s)
    per = cols * rows
    total = len(expand_items(items))
    if per <= 0 or total == 0:
        return 0
    return math.ceil(total / per)


def render_page(items, s: Settings, page_index: int, dpi: int = None) -> Image.Image:
    dpi = dpi or s.dpi
    s2 = Settings(**{**s.__dict__, "dpi": dpi})
    pw, ph = s2.paper_mm
    if s2.landscape:
        pw, ph = ph, pw
    page = Image.new("RGB", (mm_to_px(pw, dpi), mm_to_px(ph, dpi)), "white")
    cols, rows, mw, mh, rot = grid_for(s2)
    if cols * rows <= 0:
        return page
    flat = expand_items(items)
    per = cols * rows
    chunk = flat[page_index * per:(page_index + 1) * per]

    t, r, b, l = s2.margin_mm
    total_w = cols * mw + (cols - 1) * s2.gap_mm
    total_h = rows * mh + (rows - 1) * s2.gap_mm
    x0 = l + ((pw - l - r) - total_w) / 2
    y0 = t + ((ph - t - b) - total_h) / 2

    draw = ImageDraw.Draw(page)
    wpx, hpx = mm_to_px(mw, dpi), mm_to_px(mh, dpi)
    cache = {}
    for i, it in enumerate(chunk):
        row, col = divmod(i, cols)
        # RTL: ממלאים מימין לשמאל
        col = cols - 1 - col
        x = mm_to_px(x0 + col * (mw + s2.gap_mm), dpi)
        y = mm_to_px(y0 + row * (mh + s2.gap_mm), dpi)
        key = id(it)
        if key not in cache:
            cache[key] = render_magnet(it.image(), wpx, hpx, s2, rot)
        page.paste(cache[key], (x, y))
        if s2.cut_lines:
            lw = max(1, dpi // 300)
            draw.rectangle((x, y, x + wpx - 1, y + hpx - 1), outline=(150, 150, 150), width=lw)
    return page


def save_pdf(items, s: Settings, path: str, progress=None):
    n = page_count(items, s)
    pages = []
    for i in range(n):
        pages.append(render_page(items, s, i))
        if progress:
            progress(i + 1, n)
    if not pages:
        raise ValueError("אין מה לייצא")
    pages[0].save(path, "PDF", resolution=s.dpi, save_all=True, append_images=pages[1:])


def save_jpegs(items, s: Settings, base_path: str, progress=None):
    n = page_count(items, s)
    paths = []
    stem = base_path[:-4] if base_path.lower().endswith((".jpg", ".jpeg")) else base_path
    for i in range(n):
        im = render_page(items, s, i)
        p = f"{stem}.jpg" if n == 1 else f"{stem}_{i + 1}.jpg"
        im.save(p, "JPEG", quality=95, dpi=(s.dpi, s.dpi))
        paths.append(p)
        if progress:
            progress(i + 1, n)
    return paths
