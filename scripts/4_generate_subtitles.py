"""
Transcrit l'audio en cues de sous-titres avec timing par mot (Whisper local,
CPU), regroupees en paquets courts pour un rendu karaoke type Reels/TikTok.

Sort un JSON (pas un .srt/.ass) : 5_assemble.py rend chaque cue lui-meme via
caption_render.py (Pillow) plutot que de passer par un filtre ffmpeg/libass --
la fragilite de ce filtre (taille de police, timing karaoke \\k, echappement
de chemin) a cause la majorite des bugs de rendu de ce pipeline.

Usage:
    python 4_generate_subtitles.py --audio output/audio/reel_01.mp3 --out output/subs/reel_01.json
"""
import argparse
import json
from pathlib import Path

import whisper

MAX_WORDS_PER_CUE = 4


def chunk_words(segments, max_words: int = MAX_WORDS_PER_CUE) -> list[dict]:
    """
    Regroupe les mots (word_timestamps=True) en cues courtes -- une phrase
    entiere en une seule cue forcait soit un texte minuscule pour tenir dans
    la largeur du cadre, soit un debordement hors ecran a taille lisible.
    3-4 mots par cue est le standard Reels/TikTok.
    """
    words = [w for seg in segments for w in seg.get("words", [])]
    cues = []
    for i in range(0, len(words), max_words):
        group = words[i:i + max_words]
        cues.append({
            "start": group[0]["start"],
            "end": group[-1]["end"],
            "words": [
                {"text": w["word"].strip(), "start": w["start"], "end": w["end"]}
                for w in group
            ],
        })
    return cues


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
    out_path.write_text(json.dumps(chunk_words(result["segments"]), ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OK -> {out_path}")


if __name__ == "__main__":
    main()
