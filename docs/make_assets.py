"""Generate visual assets (hero banner + demo GIF) for the README.

Usage:  python docs/make_assets.py

Outputs:
    docs/hero.png  - banner image for the top of the README
    docs/demo.gif  - animated demo: page → highlight sweep → terminal extraction
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageFilter


OUT = Path(__file__).parent

# Catppuccin Mocha-inspired palette
BG = "#1e1e2e"
SURFACE = "#313244"
OVERLAY = "#45475a"
TEXT = "#cdd6f4"
SUBTLE = "#a6adc8"
ACCENT = "#89b4fa"   # blue
SECONDARY = "#89dceb"  # sky
HIGHLIGHT = (249, 226, 175)  # yellow
GREEN = "#a6e3a1"
RED = "#f38ba8"
PINK = "#f5c2e7"
TERM_BG = "#11111b"

FONT_REG = "C:/Windows/Fonts/segoeui.ttf"
FONT_BOLD = "C:/Windows/Fonts/segoeuib.ttf"
FONT_MONO = "C:/Windows/Fonts/consola.ttf"
FONT_MONO_B = "C:/Windows/Fonts/consolab.ttf"


def font(size: int, kind: str = "reg") -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(
        {"reg": FONT_REG, "bold": FONT_BOLD, "mono": FONT_MONO, "monob": FONT_MONO_B}[kind],
        size,
    )


# ---------- hero banner ----------

def make_hero():
    W, H = 1280, 380
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    # subtle vignette / accent shapes
    accent = Image.new("RGB", (W, H), BG)
    ad = ImageDraw.Draw(accent)
    ad.ellipse([-200, -200, 500, 500], fill="#313244")
    ad.ellipse([W - 400, H - 300, W + 200, H + 200], fill="#45475a")
    accent = accent.filter(ImageFilter.GaussianBlur(40))
    img = Image.blend(img, accent, 0.6)
    d = ImageDraw.Draw(img)

    # title
    d.text((60, 70), "pdf_steg", font=font(110, "bold"), fill=TEXT)

    # accent underline
    d.rectangle([62, 200, 360, 206], fill=ACCENT)

    # tagline
    d.text((62, 222), "PDF text-layer steganography",
           font=font(40, "bold"), fill=SECONDARY)
    d.text((62, 282), "render() != get_text()",
           font=font(28, "monob"), fill=SUBTLE)

    # right-side decorative "page → secret" mini-illustration
    cx = W - 360
    # page
    d.rectangle([cx, 100, cx + 220, 300], outline=OVERLAY, fill=SURFACE, width=2)
    for i in range(7):
        y = 130 + i * 22
        # most lines are gray (rasterized look)
        line_w = [180, 200, 160, 190, 170, 200, 150][i]
        d.rectangle([cx + 16, y, cx + 16 + line_w, y + 6], fill=OVERLAY)
    # one of the "lines" is actually the hidden message in accent color
    d.rectangle([cx + 16, 240, cx + 16 + 130, 246], fill=PINK)

    # arrow
    arrow_y = 200
    d.line([cx - 80, arrow_y, cx - 20, arrow_y], fill=ACCENT, width=4)
    d.polygon([cx - 20, arrow_y - 8, cx - 4, arrow_y, cx - 20, arrow_y + 8], fill=ACCENT)

    img.save(OUT / "hero.png", optimize=True)
    print("wrote", OUT / "hero.png")


# ---------- demo gif ----------

PAGE_LINES = [
    "Lorem ipsum dolor sit amet, consectetur",
    "adipiscing elit. Sed do eiusmod tempor",
    "incididunt ut labore et dolore magna",
    "aliqua. Ut enim ad minim veniam, quis",
    "nostrud exercitation ullamco laboris",
    "nisi ut aliquip ex ea commodo consequat.",
]

# 'ola mundo' (with the space) — matches the tool's default behavior, which
# tries to embed every char of the message including whitespace. The space
# gets a position in the page just like the letters do.
SECRET_LETTERS = "ola mundo"
HIDE_CMD = '$ python pdf_steg.py hide input.pdf -m "ola mundo" -o output.pdf'


def find_secret_positions() -> list[tuple[int, int]]:
    """Return [(line_idx, char_idx), ...] — one entry per secret letter, in order."""
    positions: list[tuple[int, int]] = []
    msg_idx = 0
    for li, line in enumerate(PAGE_LINES):
        ci = 0
        while ci < len(line) and msg_idx < len(SECRET_LETTERS):
            if line[ci].lower() == SECRET_LETTERS[msg_idx].lower():
                positions.append((li, ci))
                msg_idx += 1
            ci += 1
        if msg_idx >= len(SECRET_LETTERS):
            break
    return positions


SECRET_POS = find_secret_positions()


def char_bbox(line_idx: int, char_idx: int, page_x: int, page_y: int):
    f = font(18, "mono")
    char_w = f.getlength("M")
    top = page_y + 44 + line_idx * 28
    left = page_x + 18 + int(char_idx * char_w)
    return (left, top - 1, left + max(int(char_w) + 1, 9), top + 22)


def line_bbox_in_page(line_idx: int, page_x: int, page_y: int, page_w: int):
    f = font(18, "mono")
    line = PAGE_LINES[line_idx]
    w = f.getlength(line)
    top = page_y + 44 + line_idx * 28
    return (page_x + 18, top - 2, page_x + 18 + int(w) + 2, top + 22)


def draw_page(d: ImageDraw.ImageDraw, x: int, y: int, w: int, h: int,
              filename: str = "input.pdf"):
    """Render a fake PDF reader window with the lorem ipsum body."""
    d.rectangle([x, y, x + w, y + h], outline=OVERLAY, fill="#cdd6f4", width=2)
    d.rectangle([x, y, x + w, y + 26], fill="#bac2de")
    d.ellipse([x + 8, y + 8, x + 18, y + 18], fill="#f38ba8")
    d.ellipse([x + 24, y + 8, x + 34, y + 18], fill="#f9e2af")
    d.ellipse([x + 40, y + 8, x + 50, y + 18], fill="#a6e3a1")
    f_title = font(13, "reg")
    d.text((x + (w - f_title.getlength(filename)) / 2, y + 6),
           filename, font=f_title, fill="#1e1e2e")
    f = font(18, "mono")
    for i, line in enumerate(PAGE_LINES):
        d.text((x + 18, y + 44 + i * 28), line, font=f, fill="#1e1e2e")


def overlay_highlights(img: Image.Image, highlighted: set[tuple[int, int]],
                       page_x: int, page_y: int, alpha: int = 150):
    """Paint a translucent yellow rect over each highlighted (line, char) pair."""
    if not highlighted:
        return
    for (li, ci) in highlighted:
        bx0, by0, bx1, by1 = char_bbox(li, ci, page_x, page_y)
        rect = Image.new("RGBA", (bx1 - bx0, by1 - by0), HIGHLIGHT + (alpha,))
        img.paste(rect, (bx0, by0), rect)


def draw_terminal(d: ImageDraw.ImageDraw, x: int, y: int, w: int, h: int,
                  command_chars: int, status: str, prompt_blink: bool,
                  show_extracted: bool = False):
    d.rectangle([x, y, x + w, y + h], outline="#181825", fill=TERM_BG, width=1)
    d.rectangle([x, y, x + w, y + 22], fill="#181825")
    d.ellipse([x + 8, y + 6, x + 18, y + 16], fill="#f38ba8")
    d.ellipse([x + 24, y + 6, x + 34, y + 16], fill="#f9e2af")
    d.ellipse([x + 40, y + 6, x + 50, y + 16], fill="#a6e3a1")
    d.text((x + w // 2 - 26, y + 4), "terminal", font=font(13, "reg"), fill=SUBTLE)

    cmd = HIDE_CMD[:command_chars]
    d.text((x + 14, y + 36), cmd, font=font(15, "mono"), fill=GREEN)
    if prompt_blink and command_chars < len(HIDE_CMD):
        cw = font(15, "mono").getlength(cmd)
        d.rectangle([x + 14 + cw, y + 38, x + 14 + cw + 8, y + 54], fill=GREEN)

    if status == "running":
        d.text((x + 14, y + 60), "[*] embedding 8 letters at original positions...",
               font=font(15, "mono"), fill=SECONDARY)
    elif status == "done":
        d.text((x + 14, y + 60), "[ok] wrote output.pdf  (looks identical to input)",
               font=font(13, "mono"), fill=GREEN)
        if show_extracted:
            d.text((x + 14, y + 84), "$ python pdf_steg.py reveal output.pdf",
                   font=font(15, "mono"), fill=GREEN)
            d.text((x + 14, y + 108), "> ola mundo",
                   font=font(18, "monob"), fill=PINK)


def make_demo_gif():
    fw, fh = 760, 520
    page_x, page_y, page_w, page_h = 60, 40, 640, 240
    term_x, term_y, term_w, term_h = 60, 300, 640, 180
    full_secret_set = set(SECRET_POS)

    frames: list[Image.Image] = []

    # Phase 1 — idle on input.pdf, blinking prompt (8 frames)
    for fi in range(8):
        img = Image.new("RGB", (fw, fh), BG)
        d = ImageDraw.Draw(img)
        draw_page(d, page_x, page_y, page_w, page_h, filename="input.pdf")
        draw_terminal(d, term_x, term_y, term_w, term_h, 0, "", fi % 8 < 4)
        frames.append(img)

    # Phase 2 — terminal types the hide command (~one frame per 2 chars)
    for ci in range(0, len(HIDE_CMD) + 1, 2):
        img = Image.new("RGB", (fw, fh), BG)
        d = ImageDraw.Draw(img)
        draw_page(d, page_x, page_y, page_w, page_h, filename="input.pdf")
        draw_terminal(d, term_x, term_y, term_w, term_h, ci, "", True)
        frames.append(img)

    # Phase 3 — running message (6 frames), then done (4 frames)
    for _ in range(6):
        img = Image.new("RGB", (fw, fh), BG)
        d = ImageDraw.Draw(img)
        draw_page(d, page_x, page_y, page_w, page_h, filename="input.pdf")
        draw_terminal(d, term_x, term_y, term_w, term_h,
                      len(HIDE_CMD), "running", False)
        frames.append(img)
    for _ in range(4):
        img = Image.new("RGB", (fw, fh), BG)
        d = ImageDraw.Draw(img)
        draw_page(d, page_x, page_y, page_w, page_h, filename="output.pdf")
        draw_terminal(d, term_x, term_y, term_w, term_h,
                      len(HIDE_CMD), "done", False)
        frames.append(img)

    # Phase 4 — highlighter sweeps line-by-line, but only the secret letters
    # actually catch the highlight (the rest is image, untouchable).
    n_lines = len(PAGE_LINES)
    frames_per_line = 6
    highlighted: set[tuple[int, int]] = set()
    for li in range(n_lines):
        line_text = PAGE_LINES[li]
        lbx0, lby0, lbx1, lby1 = line_bbox_in_page(li, page_x, page_y, page_w)
        for k in range(frames_per_line):
            progress = (k + 1) / frames_per_line
            cursor_x = int(lbx0 + (lbx1 - lbx0) * progress)
            # Mark every secret position the sweep has already passed.
            for (sli, sci) in SECRET_POS:
                if sli < li:
                    highlighted.add((sli, sci))
                elif sli == li:
                    cbx0, _, cbx1, _ = char_bbox(sli, sci, page_x, page_y)
                    if cursor_x >= (cbx0 + cbx1) // 2:
                        highlighted.add((sli, sci))

            img = Image.new("RGB", (fw, fh), BG)
            d = ImageDraw.Draw(img)
            draw_page(d, page_x, page_y, page_w, page_h, filename="output.pdf")
            overlay_highlights(img, highlighted, page_x, page_y, alpha=180)

            # highlighter "tip" floating along the current line
            d2 = ImageDraw.Draw(img)
            tip_y = lby0
            d2.polygon([
                (cursor_x, tip_y - 4),
                (cursor_x + 12, tip_y - 14),
                (cursor_x + 22, tip_y - 4),
                (cursor_x + 18, tip_y + 4),
                (cursor_x + 6, tip_y + 4),
            ], fill="#f9e2af", outline="#fab387")
            d2.line([(cursor_x + 12, tip_y - 14), (cursor_x + 12, tip_y + 4)],
                    fill="#fab387", width=1)

            draw_terminal(d2, term_x, term_y, term_w, term_h,
                          len(HIDE_CMD), "done", False)
            frames.append(img)

    # Phase 5 — final state + extracted message in the terminal (18 frames)
    for fi in range(18):
        img = Image.new("RGB", (fw, fh), BG)
        d = ImageDraw.Draw(img)
        draw_page(d, page_x, page_y, page_w, page_h, filename="output.pdf")
        overlay_highlights(img, full_secret_set, page_x, page_y, alpha=200)
        draw_terminal(ImageDraw.Draw(img), term_x, term_y, term_w, term_h,
                      len(HIDE_CMD), "done", False, show_extracted=fi >= 3)
        frames.append(img)

    palette_img = frames[-1].convert("P", palette=Image.Palette.ADAPTIVE, colors=128)
    pal_frames = [
        f.convert("RGB").quantize(palette=palette_img, dither=Image.Dither.NONE)
        for f in frames
    ]
    pal_frames[0].save(
        OUT / "demo.gif",
        save_all=True,
        append_images=pal_frames[1:],
        duration=70,
        loop=0,
        optimize=True,
        disposal=2,
    )
    print(f"wrote {OUT / 'demo.gif'} ({len(frames)} frames)")


if __name__ == "__main__":
    make_hero()
    make_demo_gif()
