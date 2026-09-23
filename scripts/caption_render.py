"""
Rendu PIL des sous-titres karaoke (mot surligne pendant qu'il est prononce).

Remplace le pipeline precedent (.ass + libass via le filtre `subtitles`
ffmpeg) : les bugs recents (police surdimensionnee, timing \\k mal calcule,
echappement de chemin) venaient tous de la fragilite d'un filtre ffmpeg
construit comme une chaine de caracteres. Rendre chaque cue en image PNG
avec Pillow est verifiable directement (on peut ouvrir l'image et regarder),
et 5_assemble.py se contente de la positionner/composer via moviepy.
"""
from PIL import Image, ImageDraw, ImageFont

import catalog

FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_SIZE = 58
CTA_FONT_SIZE = 68  # derniere cue (appel a l'action) : plus grande, plus visible
HIGHLIGHT_COLOR = (255, 215, 0, 255)   # ambre/doré : mot en cours
DEFAULT_COLOR = (255, 255, 255, 255)   # blanc : mots pas encore prononces
OUTLINE_COLOR = (0, 0, 0, 255)
OUTLINE_WIDTH = 4
MAX_WIDTH = 900  # marge de securite des deux cotes d'un cadre 1080px de large
WORD_GAP = 18
CTA_PILL_COLOR = (17, 24, 39, 235)     # navy fonce : pastille derriere le CTA final
CTA_PILL_PADDING = 24
CTA_PILL_RADIUS = 32


def _font(size: int = FONT_SIZE):
    return ImageFont.truetype(FONT_PATH, size)


def caption_style(theme: dict | None) -> dict:
    """Style des sous-titres d'un theme (catalog/themes.json) ; None -> style historique."""
    if not theme:
        return {"font": FONT_PATH, "size": FONT_SIZE, "cta_size": CTA_FONT_SIZE, "upper": False,
                "outline": OUTLINE_WIDTH, "fg": DEFAULT_COLOR, "hl": HIGHLIGHT_COLOR,
                "stroke": OUTLINE_COLOR, "pill": CTA_PILL_COLOR}
    st, c = theme.get("sous_titres", {}), theme["couleurs"]
    size = int(st.get("taille", FONT_SIZE))
    return {"font": catalog.font_path(theme, "texte"), "size": size, "cta_size": round(size * CTA_FONT_SIZE / FONT_SIZE),
            "upper": bool(st.get("majuscules")), "outline": int(st.get("contour", OUTLINE_WIDTH)),
            "fg": catalog.hex_to_rgba(c["texte"]), "hl": catalog.hex_to_rgba(c["surligne"]),
            "stroke": catalog.hex_to_rgba(c["contour"]), "pill": catalog.hex_to_rgba(c["pastille"], 235)}


def render_caption(words: list[str], active_index: int, emphasize: bool = False,
                   theme: dict | None = None) -> Image.Image:
    """
    words: mots de la cue (deja nettoyes, sans espaces superflus).
    active_index: index du mot actuellement prononce (surligne).
    emphasize: True pour la derniere cue du reel (l'appel a l'action) --
    police plus grande sur une pastille de fond, pour qu'elle se distingue
    nettement des sous-titres precedents au lieu de se fondre dans le reste.
    Retourne une image RGBA rognee au texte, prete a composer par-dessus
    la video (fond transparent).
    """
    style = caption_style(theme)
    font = ImageFont.truetype(style["font"], style["cta_size"] if emphasize else style["size"])
    outline = style["outline"]
    if style["upper"]:
        words = [w.upper() for w in words]
    dummy = Image.new("RGBA", (10, 10))
    draw = ImageDraw.Draw(dummy)

    word_sizes = []
    # Decalage du trace par rapport a son origine (non nul, surtout en
    # hauteur, pour les polices a grand interligne comme Poppins) : sans le
    # compenser, le bas des lettres (ou le haut des accents) sortait de l'image.
    word_offsets = []
    for w in words:
        bbox = draw.textbbox((0, 0), w, font=font, stroke_width=outline)
        word_sizes.append((bbox[2] - bbox[0], bbox[3] - bbox[1]))
        word_offsets.append((bbox[0], bbox[1], bbox[3]))

    # Retour a la ligne simple si la cue depasse la largeur max (rare avec
    # MAX_WORDS_PER_CUE=4, mais un mot compose long peut suffire a deborder).
    lines: list[list[int]] = [[]]
    line_width = 0
    for i, (w_width, _) in enumerate(word_sizes):
        added = w_width + (WORD_GAP if lines[-1] else 0)
        if line_width + added > MAX_WIDTH and lines[-1]:
            lines.append([])
            line_width = 0
            added = w_width
        lines[-1].append(i)
        line_width += added

    # Hauteur de ligne = du plus haut au plus bas trace de la ligne (accents
    # compris) ; tous les mots d'une ligne partagent le meme decalage vertical
    # pour rester sur la meme ligne de base.
    line_tops = [min(word_offsets[i][1] for i in line) for line in lines]
    line_heights = [max(word_offsets[i][2] for i in line) - top for line, top in zip(lines, line_tops)]
    total_height = sum(line_heights) + WORD_GAP * (len(lines) - 1)
    total_width = max(
        sum(word_sizes[i][0] for i in line) + WORD_GAP * (len(line) - 1)
        for line in lines
    )

    pad = outline * 2 + (CTA_PILL_PADDING if emphasize else 0)
    img = Image.new("RGBA", (total_width + pad * 2, total_height + pad * 2), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    if emphasize:
        draw.rounded_rectangle(
            [0, 0, img.width - 1, img.height - 1], radius=CTA_PILL_RADIUS, fill=style["pill"]
        )

    y = pad
    for line, line_h, line_top in zip(lines, line_heights, line_tops):
        line_w = sum(word_sizes[i][0] for i in line) + WORD_GAP * (len(line) - 1)
        x = pad + (total_width - line_w) // 2
        for i in line:
            color = style["hl"] if i == active_index else style["fg"]
            draw.text((x - word_offsets[i][0], y - line_top), words[i], font=font, fill=color,
                      stroke_width=outline, stroke_fill=style["stroke"])
            x += word_sizes[i][0] + WORD_GAP
        y += line_h + WORD_GAP

    return img
