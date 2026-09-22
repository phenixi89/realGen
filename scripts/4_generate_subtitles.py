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


def write_srt(segments, out_path: Path):
    lines = []
    for i, seg in enumerate(segments, 1):
        start = format_timestamp(seg["start"])
        end = format_timestamp(seg["end"])
        text = seg["text"].strip()
        lines.append(f"{i}\n{start} --> {end}\n{text}\n")
    out_path.write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--audio", type=str, required=True)
    parser.add_argument("--out", type=str, required=True)
    parser.add_argument("--model", type=str, default="base",
                         help="tiny/base/small (base = bon compromis vitesse/precision en CPU)")
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
    result = model.transcribe(args.audio, language="fr", word_timestamps=False)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    write_srt(result["segments"], out_path)
    print(f"OK -> {out_path}")


if __name__ == "__main__":
    main()
