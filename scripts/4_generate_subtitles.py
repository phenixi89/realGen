"""
Genere des sous-titres synchronises (mot par mot) depuis un fichier audio, via Whisper (local, CPU).

Usage:
    python 4_generate_subtitles.py --audio output/audio/reel_01.mp3 --out output/subs/reel_01.srt
"""
import argparse
from pathlib import Path

import whisper


def format_timestamp(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


MAX_WORDS_PER_CUE = 4


def chunk_words(segments, max_words: int = MAX_WORDS_PER_CUE) -> list[dict]:
    """
    Regroupe les mots (word_timestamps=True) en cues courtes -- une phrase
    entiere en une seule cue (comportement precedent) forcait soit un texte
    minuscule pour tenir dans la largeur du cadre, soit un debordement hors
    ecran a taille lisible. 3-4 mots par cue est le style standard des
    sous-titres Reels/TikTok, et reste lisible a une taille de police normale.
    """
    words = [w for seg in segments for w in seg.get("words", [])]
    cues = []
    for i in range(0, len(words), max_words):
        group = words[i:i + max_words]
        cues.append({
            "start": group[0]["start"],
            "end": group[-1]["end"],
            "text": "".join(w["word"] for w in group).strip(),
        })
    return cues


def write_srt(cues, out_path: Path):
    lines = []
    for i, cue in enumerate(cues, 1):
        start = format_timestamp(cue["start"])
        end = format_timestamp(cue["end"])
        lines.append(f"{i}\n{start} --> {end}\n{cue['text']}\n")
    out_path.write_text("\n".join(lines), encoding="utf-8")


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
    write_srt(chunk_words(result["segments"]), out_path)
    print(f"OK -> {out_path}")


if __name__ == "__main__":
    main()
