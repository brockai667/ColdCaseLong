#!/usr/bin/env python3
"""Auto YouTube thumbnail: dramaticky frame z videa + velky bold titulok (lepsie CTR)."""
import os, subprocess


def _font(size):
    from PIL import ImageFont
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
              "C:/Windows/Fonts/arialbd.ttf", "C:/Windows/Fonts/ariblk.ttf",
              "C:/Windows/Fonts/arial.ttf"):
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def make_thumbnail(video, title, ffmpeg, ffprobe, out_jpg):
    from PIL import Image, ImageDraw, ImageOps
    W, H = 1280, 720
    frame = out_jpg + ".frame.jpg"
    try:
        d = float(subprocess.run([ffprobe, "-v", "error", "-show_entries", "format=duration",
                                  "-of", "default=nw=1:nk=1", video],
                                 capture_output=True, text=True).stdout.strip())
    except Exception:
        d = 60.0
    t = max(2.0, d * 0.2)
    subprocess.run([ffmpeg, "-y", "-ss", str(t), "-i", video, "-frames:v", "1", "-q:v", "2", frame],
                   capture_output=True)
    im0 = Image.open(frame).convert("RGB")
    w0, h0 = im0.size
    im0 = im0.crop((0, 0, w0, int(h0 * 0.86)))   # odrez spodny pruh s titulkami z videa
    img = ImageOps.fit(im0, (W, H))
    # tmavy gradient zdola -> citatelny text
    grad = Image.new("L", (1, H), 0)
    for y in range(H):
        grad.putpixel((0, y), int(min(225, max(0, (y - H * 0.33) / (H * 0.67) * 225))))
    img = Image.composite(Image.new("RGB", (W, H), (0, 0, 0)), img, grad.resize((W, H)))
    draw = ImageDraw.Draw(img)
    font = _font(98)
    # zalom titulok podla sirky
    words = title.upper().split()
    lines, cur = [], ""
    for w in words:
        test = (cur + " " + w).strip()
        if draw.textlength(test, font=font) > W - 110 and cur:
            lines.append(cur); cur = w
        else:
            cur = test
    if cur:
        lines.append(cur)
    lines = lines[:3]
    lh = 112
    y = H - 55 - lh * len(lines)
    for ln in lines:
        x = (W - draw.textlength(ln, font=font)) // 2
        for dx in (-3, 0, 3):
            for dy in (-3, 0, 3):
                draw.text((x + dx, y + dy), ln, font=font, fill=(0, 0, 0))
        draw.text((x, y), ln, font=font, fill=(255, 224, 54))
        y += lh
    img.save(out_jpg, "JPEG", quality=88)
    try:
        os.remove(frame)
    except OSError:
        pass
    return out_jpg
