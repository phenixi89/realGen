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
