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

FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_SIZE = 58
HIGHLIGHT_COLOR = (255, 215, 0, 255)   # ambre/doré : mot en cours
DEFAULT_COLOR = (255, 255, 255, 255)   # blanc : mots pas encore prononces
OUTLINE_COLOR = (0, 0, 0, 255)
OUTLINE_WIDTH = 4
MAX_WIDTH = 900  # marge de securite des deux cotes d'un cadre 1080px de large
WORD_GAP = 18


def _font():
    return ImageFont.truetype(FONT_PATH, FONT_SIZE)


def render_caption(words: list[str], active_index: int) -> Image.Image:
    """
    words: mots de la cue (deja nettoyes, sans espaces superflus).
    active_index: index du mot actuellement prononce (surligne).
    Retourne une image RGBA rognee au texte, prete a composer par-dessus
    la video (fond transparent).
    """
    font = _font()
    dummy = Image.new("RGBA", (10, 10))
    draw = ImageDraw.Draw(dummy)

    word_sizes = []
    for w in words:
        bbox = draw.textbbox((0, 0), w, font=font, stroke_width=OUTLINE_WIDTH)
        word_sizes.append((bbox[2] - bbox[0], bbox[3] - bbox[1]))

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

    line_heights = [max(word_sizes[i][1] for i in line) for line in lines]
    total_height = sum(line_heights) + WORD_GAP * (len(lines) - 1)
    total_width = max(
        sum(word_sizes[i][0] for i in line) + WORD_GAP * (len(line) - 1)
        for line in lines
    )

    pad = OUTLINE_WIDTH * 2
    img = Image.new("RGBA", (total_width + pad * 2, total_height + pad * 2), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    y = pad
    for line, line_h in zip(lines, line_heights):
        line_w = sum(word_sizes[i][0] for i in line) + WORD_GAP * (len(line) - 1)
        x = pad + (total_width - line_w) // 2
        for i in line:
            color = HIGHLIGHT_COLOR if i == active_index else DEFAULT_COLOR
            draw.text((x, y), words[i], font=font, fill=color,
                      stroke_width=OUTLINE_WIDTH, stroke_fill=OUTLINE_COLOR)
            x += word_sizes[i][0] + WORD_GAP
        y += line_h + WORD_GAP

    return img
