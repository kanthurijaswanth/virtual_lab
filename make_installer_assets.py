# make_installer_assets.py
from PIL import Image, ImageMath
from pathlib import Path

ASSETS = Path("assets")
SRC = ASSETS / "mmt_logo.png"
ASSETS.mkdir(exist_ok=True)

if not SRC.exists():
    raise FileNotFoundError(f"Put your PNG at {SRC}")

def premultiply_alpha(img: Image.Image) -> Image.Image:
    """Return an RGBA image with premultiplied RGB (better for Inno alpha)."""
    img = img.convert("RGBA")
    r, g, b, a = img.split()
    r = ImageMath.eval("convert(r*a/255, 'L')", r=r, a=a)
    g = ImageMath.eval("convert(g*a/255, 'L')", g=g, a=a)
    b = ImageMath.eval("convert(b*a/255, 'L')", b=b, a=a)
    return Image.merge("RGBA", (r, g, b, a))

# Load once
base = Image.open(SRC).convert("RGBA")

# --- 1) ICO for installer/uninstaller/app icon (multi-size) ---
sizes = [(256,256),(128,128),(64,64),(48,48),(32,32),(16,16)]
ico_out = ASSETS / "cots.ico"
base.save(ico_out, sizes=sizes)
print(f"✔ wrote {ico_out}")

# --- 2) Wizard images (BMP) ---
# Big left banner (good hi-DPI size)
big_size = (240, 459)
small_size = (147, 147)

def save_bmp(out_path: Path, size):
    im = base.resize(size, Image.LANCZOS)
    im = premultiply_alpha(im)
    im.save(out_path, format="BMP")
    print(f"✔ wrote {out_path}")

save_bmp(ASSETS / "wizard-big.bmp", big_size)
save_bmp(ASSETS / "wizard-small.bmp", small_size)
