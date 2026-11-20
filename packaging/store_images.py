"""Builds Chrome Web Store images from docs/store/popup-live.png:
docs/store/screenshot-1280x800.png and docs/store/promo-440x280.png."""
import os
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
S = os.path.join(ROOT, "docs", "store")


def font(size):
    for p in ("/System/Library/Fonts/Helvetica.ttc", "/System/Library/Fonts/Supplemental/Arial.ttf"):
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


popup = Image.open(os.path.join(S, "popup-live.png")).convert("RGB")
# Crop the popup page to its content plus a margin (the page screenshot is viewport-sized).
from PIL import ImageChops
bg = Image.new("RGB", popup.size, popup.getpixel((popup.width - 1, popup.height - 1)))
l, t, r, b = ImageChops.difference(popup, bg).getbbox()
popup = popup.crop((max(l - 24, 0), max(t - 24, 0), min(r + 24, popup.width), min(b + 24, popup.height)))
shot = Image.new("RGB", (1280, 800), "white")
d = ImageDraw.Draw(shot)
d.text((80, 90), "Predictive Loading", fill="black", font=font(56))
lines = ["Learns which page you open next on each site,", "from your own history, and loads it early.",
         "", "Permission: storage only.", "Stores only SHA-256 hashes, on your device.",
         "Never preloads logout, delete,", "cart or checkout links."]
for i, t in enumerate(lines):
    d.text((80, 200 + 44 * i), t, fill="black", font=font(28))
scale = min(460 / popup.width, 600 / popup.height, 3.0)
p = popup.resize((int(popup.width * scale), int(popup.height * scale)))
x, y = 1280 - 80 - p.width, (800 - p.height) // 2
d.rectangle((x - 2, y - 2, x + p.width + 1, y + p.height + 1), outline="black", width=2)
shot.paste(p, (x, y))
shot.save(os.path.join(S, "screenshot-1280x800.png"))
promo = Image.new("RGB", (440, 280), "white")
d = ImageDraw.Draw(promo)
d.text((30, 90), "Predictive Loading", fill="black", font=font(36))
d.text((30, 150), "Your next page, loaded early.", fill="black", font=font(22))
promo.save(os.path.join(S, "promo-440x280.png"))
print("store images written")
