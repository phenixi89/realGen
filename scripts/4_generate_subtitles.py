"""
Genere des sous-titres karaoke (surlignage mot par mot, comme sur les Reels
qui marchent) depuis un fichier audio, via Whisper (local, CPU). Produit un
.ass (pas un .srt) : c'est le seul format qui porte le timing par mot dont
libass a besoin pour surligner progressivement.

Usage:
    python 4_generate_subtitles.py --audio output/audio/reel_01.mp3 --out output/subs/reel_01.ass
"""
import argparse
from pathlib import Path

import whisper

MAX_WORDS_PER_CUE = 4

# Format ASS : &HAABBGGRR. PrimaryColour = couleur du mot deja prononce
# (surlignage), SecondaryColour = mots pas encore prononces dans la meme
# cue. \k (karaoke) bascule l'un vers l'autre au fil du temps -- c'est ce
# qui donne l'effet "mot qui s'allume en le disant" plutot qu'un bloc de
# texte statique.
ASS_HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,DejaVu Sans,58,&H0000D7FF,&H00FFFFFF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,4,0,2,60,60,170,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def format_timestamp(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h:d}:{m:02d}:{s:05.2f}"


def chunk_words(segments, max_words: int = MAX_WORDS_PER_CUE) -> list[dict]:
    """
    Regroupe les mots (word_timestamps=True) en cues courtes -- une phrase
    entiere en une seule cue forcait soit un texte minuscule pour tenir dans
    la largeur du cadre, soit un debordement hors ecran a taille lisible.
    3-4 mots par cue est le standard Reels/TikTok, et garde les mots (pas
    juste le texte fusionne) pour le surlignage karaoke par mot.
    """
    words = [w for seg in segments for w in seg.get("words", [])]
    cues = []
    for i in range(0, len(words), max_words):
        group = words[i:i + max_words]
        cues.append({"start": group[0]["start"], "end": group[-1]["end"], "words": group})
    return cues


def write_ass(cues: list[dict], out_path: Path):
    lines = [ASS_HEADER]
    for cue in cues:
        start = format_timestamp(cue["start"])
        end = format_timestamp(cue["end"])
        # \k prend une duree en centiemes de seconde : le mot reste en
        # SecondaryColour jusqu'a ce que ce delai soit ecoule depuis le
        # debut de la cue, puis bascule en PrimaryColour.
        text = "".join(
            f"{{\\k{max(round((w['end'] - w['start']) * 100), 1)}}}{w['word'].strip()} "
            for w in cue["words"]
        ).strip()
        lines.append(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{text}")
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--audio", type=str, required=True)
    parser.add_argument("--out", type=str, required=True)
    parser.add_argument("--model", type=str, default="small",
                         help="tiny/base/small (small = nettement plus precis que base, "
                              "reste rapide en CPU sur un clip de 15-20s)")
    parser.add_argument("--force", action="store_true",
                         help="Regenere meme si --out existe deja")
    args = parser.parse_args()

    out_path = Path(args.out)
    if not args.force and out_path.exists():
        print(f"REPRISE: {out_path} existe deja, on saute (--force pour regenerer)")
        return

    print(f"Chargement du modele Whisper '{args.model}'...")
    model = whisper.load_model(args.model)

    print(f"Transcription de {args.audio}...")
    result = model.transcribe(args.audio, language="fr", word_timestamps=True)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    write_ass(chunk_words(result["segments"]), out_path)
    print(f"OK -> {out_path}")


if __name__ == "__main__":
    main()
