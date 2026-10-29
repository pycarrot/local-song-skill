# Render a karaoke lyric video from word timings (w2lines.py output).
# Usage: TITLE="song name" [TOP=b5a0de BOTTOM=5c488c] lyricvid.py <lines.json> <audio> <out.mp4> [seconds]
import os, sys, json, subprocess, numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
src, audio, out = sys.argv[1:4]
W, H, FPS = 1280, 720, 24
d = json.load(open(src))
DUR = float(sys.argv[4]) if len(sys.argv) > 4 else float(subprocess.check_output(
    ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", audio]))
lines = [{"t0": l["start"] / 1000, "t1": l["end"] / 1000, "words": [(w["start"] / 1000, w["text"].strip()) for w in l["words"]]}
         for s in d["lyrics_sections"] for l in s["lines"]]
for a, b in zip(lines, lines[1:] + [None]):  # hold each line until the next starts (max +2.5s)
    a["hold"] = min(b["t0"], a["t1"] + 2.5) if b else a["t1"] + 3

def F(size, w="Medium"):
    try:  # macOS
        return ImageFont.truetype("/System/Library/Fonts/Avenir Next.ttc", size, index={"Medium": 5, "Bold": 0, "UltraLight": 8}[w])
    except OSError:
        for f in ("DejaVuSans-Bold.ttf" if w == "Bold" else "DejaVuSans.ttf", "Arial.ttf", "arial.ttf"):
            try: return ImageFont.truetype(f, size)
            except OSError: pass
        return ImageFont.load_default(size)
big, small, title, sub = F(54, "Bold"), F(30), F(110, "UltraLight"), F(26)

# background: two-colour gradient (default lavender) + slow drifting soft light blobs, computed small then upscaled
gy, gx = np.mgrid[0:90, 0:160].astype(np.float32)
hexrgb = lambda h: np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)])
top, bot = hexrgb(os.environ.get("TOP", "b5a0de")), hexrgb(os.environ.get("BOTTOM", "5c488c"))
base = top[None, None] * (1 - gy[..., None] / 90) + bot[None, None] * (gy[..., None] / 90)
blobs = [(0.11, 0.07, 40, 30, (255, 214, 236)), (0.07, 0.13, 120, 60, (214, 236, 255)), (0.05, 0.09, 80, 20, (255, 240, 220))]
def bg(t):
    img = base.copy()
    for i, (fx, fy, cx, cy, col) in enumerate(blobs):
        x = cx + 35 * np.sin(t * fx + i); y = cy + 18 * np.cos(t * fy + 2 * i)
        m = np.exp(-((gx - x) ** 2 + (gy - y) ** 2) / (2 * 22 ** 2))[..., None] * 0.45
        img = img * (1 - m) + np.array(col) * m
    return Image.fromarray(img.clip(0, 255).astype(np.uint8)).resize((W, H), Image.BICUBIC)

def ease(x): return max(0.0, min(1.0, x))

def draw_line(layer, ln, t, y, font, alpha, karaoke):
    dr = ImageDraw.Draw(layer)
    words = [w for _, w in ln["words"]]; sp = dr.textlength(" ", font=font)
    widths = [dr.textlength(w, font=font) for w in words]
    x = (W - sum(widths) - sp * (len(words) - 1)) / 2
    for (ws, w), wd in zip(ln["words"], widths):
        lit = ease((t - ws) / 0.18) if karaoke else 0
        a = int(alpha * (110 + 145 * lit))
        dr.text((x, y), w, font=font, fill=(255, 255, 255, a), anchor="ls")
        x += wd + sp

def frame(t):
    im = bg(t).convert("RGBA")
    txt = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dr = ImageDraw.Draw(txt)
    first = lines[0]["t0"]
    if t < first - 0.5:  # title card
        a = ease(t / 1.5) * ease((first - 0.5 - t) / 1.2)
        dr.text((W / 2, H / 2 - 10), os.environ.get("TITLE", "untitled"), font=title, fill=(255, 255, 255, int(255 * a)), anchor="ms")
        dr.text((W / 2, H / 2 + 48), "an original song", font=sub, fill=(255, 255, 255, int(170 * a)), anchor="ms")
    cur = next((l for l in lines if l["t0"] - 0.4 <= t < l["hold"]), None)
    if cur:
        a = ease((t - cur["t0"] + 0.4) / 0.4) * ease((cur["hold"] - t) / 0.35)
        draw_line(txt, cur, t, H / 2 + 18, big, a, True)
        i = lines.index(cur)
        if i + 1 < len(lines) and lines[i + 1]["t0"] - cur["hold"] < 1.0:
            draw_line(txt, lines[i + 1], t, H / 2 + 80, small, a * 0.7, False)
    elif t > first:  # instrumental gap
        nxt = next((l for l in lines if l["t0"] > t), None)
        prv = max((l["hold"] for l in lines if l["hold"] <= t), default=0)
        if nxt is None or nxt["t0"] - prv > 4:
            a = ease((t - prv) / 1.0) * (ease((nxt["t0"] - 0.6 - t) / 0.8) if nxt else ease((DUR - 2 - t) / 2))
            dr.text((W / 2, H / 2 + 18), "•  •  •", font=small, fill=(255, 255, 255, int(150 * a * (0.6 + 0.4 * np.sin(t * 3)))), anchor="ms")
    shadow = Image.new("RGBA", (W, H), (60, 30, 90, 0)); shadow.putalpha(txt.getchannel("A").point(lambda v: v // 3))
    im.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(8)))
    im.alpha_composite(txt)
    return im.convert("RGB")

if __name__ == "__main__":
    p = subprocess.Popen(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
                          "-i", "-", "-i", audio, "-t", str(DUR), "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
                          "-c:a", "aac", "-b:a", "256k", "-shortest", "-movflags", "+faststart", out], stdin=subprocess.PIPE)
    for n in range(int(DUR * FPS)):
        p.stdin.write(frame(n / FPS).tobytes())
    p.stdin.close(); sys.exit(p.wait())
