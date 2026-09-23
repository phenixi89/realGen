"""
Compose une "scene" de montage a partir de deux captures Playwright : le
viewport entier (fond, floute) et un element precis du DOM (carte nette, au
premier plan). Remplace l'ancienne approche "un plein-ecran recadre en
paysage->portrait" : chaque scene est deja a la bonne taille verticale, sans
perte de contenu sur les bords.
"""
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageOps

OUT_SIZE = (1080, 1920)
CARD_MAX_WIDTH = 940
CARD_MAX_HEIGHT_RATIO = 0.72
CORNER_RADIUS = 28
BLUR_RADIUS = 30
BG_BRIGHTNESS = 0.55
SHADOW_OFFSET_Y = 18
SHADOW_BLUR = 24
MAX_UPSCALE = 2.5


def _rounded_mask(size: tuple[int, int], radius: int) -> Image.Image:
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, size[0] - 1, size[1] - 1], radius=radius, fill=255)
    return mask


def card_rect(fg_size: tuple[int, int]) -> tuple[int, int, int, int]:
    """
    (x, y, largeur, hauteur) de la carte nette dans la scene 1080x1920 :
    l'element capture, mis a l'echelle pour tenir confortablement dans le
    cadre (upscale limite pour ne pas rendre un petit element flou), centre.
    Expose a part pour le souligne anime (assets/anim/highlight.html).
    """
    max_h = int(OUT_SIZE[1] * CARD_MAX_HEIGHT_RATIO)
    scale = min(CARD_MAX_WIDTH / fg_size[0], max_h / fg_size[1], MAX_UPSCALE)
    w, h = max(int(fg_size[0] * scale), 1), max(int(fg_size[1] * scale), 1)
    return (OUT_SIZE[0] - w) // 2, (OUT_SIZE[1] - h) // 2, w, h


def compose_scene(bg_img: Image.Image, fg_img: Image.Image) -> Image.Image:
    # Fond : cover-fit + flou + assombri, pour ne jamais laisser de bande vide
    # et faire ressortir la carte nette par-dessus.
    bg = ImageOps.fit(bg_img.convert("RGB"), OUT_SIZE, method=Image.LANCZOS)
    bg = bg.filter(ImageFilter.GaussianBlur(BLUR_RADIUS))
    bg = ImageEnhance.Brightness(bg).enhance(BG_BRIGHTNESS)
    scene = bg.convert("RGBA")

    card_x, card_y, card_w, card_h = card_rect(fg_img.size)
    card_size = (card_w, card_h)
    card = fg_img.convert("RGB").resize(card_size, Image.LANCZOS)
    mask = _rounded_mask(card_size, CORNER_RADIUS)

    # Ombre portee : forme pleine decalee vers le bas, floutee, sous la carte.
    shadow_layer = Image.new("RGBA", OUT_SIZE, (0, 0, 0, 0))
    shadow_shape = Image.new("RGBA", card_size, (0, 0, 0, 190))
    shadow_layer.paste(shadow_shape, (card_x, card_y + SHADOW_OFFSET_Y), mask)
    shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(SHADOW_BLUR))
    scene = Image.alpha_composite(scene, shadow_layer)

    scene.paste(card, (card_x, card_y), mask)
    return scene.convert("RGB")


# ---------------------------------------------------------------------------
# Habillage au montage (3b) : fond aux couleurs du theme + fenetre de navigateur
# ---------------------------------------------------------------------------

CHROME_H = 58
FRAME_RADIUS = 30
URL_TEXT = "opuscv.fr"
FRAME_FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def _rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def themed_background(scene: Image.Image, colors: dict, seed: int = 0) -> Image.Image:
    """
    Degrade diagonal fond -> primaire, deux halos flous (primaire, secondaire)
    places selon seed (varie d'une capture a l'autre), et un souvenir de la
    capture floutee en transparence : le fond "appartient" au reel, pas a l'app.
    """
    import numpy as np

    w, h = OUT_SIZE
    fond, c1, c2 = (np.array(_rgb(colors[k]), dtype=float) for k in ("fond", "primaire", "secondaire"))
    yy, xx = np.mgrid[0:h, 0:w]
    k = np.clip((xx / w * 0.35 + yy / h * 0.65), 0, 1)[..., None]
    grad = fond * (1 - k * 0.55) + c1 * (k * 0.55)
    bg = Image.fromarray(grad.astype("uint8"), "RGB")
    glow = Image.new("RGB", OUT_SIZE, (0, 0, 0))
    d = ImageDraw.Draw(glow)
    spots = [(0.15, 0.12), (0.85, 0.2), (0.8, 0.85), (0.2, 0.9), (0.5, 0.05)]
    for j, color in enumerate((c1, c2)):
        cx, cy = spots[(seed + j * 2) % len(spots)]
        r = 420 - j * 80
        d.ellipse([cx * w - r, cy * h - r, cx * w + r, cy * h + r], fill=tuple(int(v) for v in color))
    glow = glow.filter(ImageFilter.GaussianBlur(160))
    bg = Image.blend(bg, Image.composite(glow, bg, glow.convert("L").point(lambda v: min(255, v * 2))), 0.55)
    ghost = ImageEnhance.Brightness(scene.convert("RGB").filter(ImageFilter.GaussianBlur(40))).enhance(0.8)
    return Image.blend(bg, ghost, 0.18)


def frame_scene(scene: Image.Image, card: list[int], theme: dict, seed: int = 0) -> Image.Image:
    """
    Recompose une capture (compose_scene) avec l'habillage du theme : la carte
    nette (card = [x, y, w, h], captures.json) garde exactement sa place --
    le souligne et le curseur restent alignes -- dans une fenetre de
    navigateur (barre a 3 pastilles + adresse), sur un fond aux couleurs du
    theme, avec ombre et liseré lumineux.
    """
    colors = theme["couleurs"]
    x, y, w, h = card
    sharp = scene.convert("RGB").crop((x, y, x + w, y + h))
    out = themed_background(scene, colors, seed).convert("RGBA")

    win_y = max(y - CHROME_H, 0)
    win_h = y + h - win_y
    win_size = (w, win_h)
    win_mask = _rounded_mask(win_size, FRAME_RADIUS)

    # Ombre portee + halo de la couleur primaire.
    for color, alpha, blur, dy in (((0, 0, 0), 200, 40, 30), (_rgb(colors["primaire"]), 120, 26, 0)):
        layer = Image.new("RGBA", OUT_SIZE, (0, 0, 0, 0))
        layer.paste(Image.new("RGBA", win_size, (*color, alpha)), (x, win_y + dy), win_mask)
        out = Image.alpha_composite(out, layer.filter(ImageFilter.GaussianBlur(blur)))

    window = Image.new("RGB", win_size, _rgb(colors.get("pastille", "#111827")))
    window.paste(sharp, (0, y - win_y))
    wd = ImageDraw.Draw(window)
    bar_h = y - win_y
    if bar_h >= 30:
        cy = bar_h // 2
        for i, dot in enumerate(((255, 95, 87), (254, 188, 46), (40, 200, 64))):
            cx = 30 + i * 30
            wd.ellipse([cx - 9, cy - 9, cx + 9, cy + 9], fill=dot)
        from PIL import ImageFont
        font = ImageFont.truetype(FRAME_FONT, 22)
        pill_w = min(360, w - 200)
        px = (w - pill_w) // 2
        wd.rounded_rectangle([px, cy - 17, px + pill_w, cy + 17], radius=17, fill=(60, 60, 72))
        wd.text((w // 2, cy), URL_TEXT, font=font, fill=(230, 230, 240), anchor="mm")
    out.paste(window, (x, win_y), win_mask)
    ImageDraw.Draw(out).rounded_rectangle([x, win_y, x + w - 1, win_y + win_h - 1], radius=FRAME_RADIUS,
                                          outline=(255, 255, 255, 60), width=2)
    return out.convert("RGB")
