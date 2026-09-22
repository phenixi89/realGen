"""
Assemble video demo + voix off + sous-titres burn-in en un MP4 final pret pour TikTok/Reels.

Usage:
    python 5_assemble.py --video output/video/demo_raw.webm \
                          --audio output/audio/reel_01.mp3 \
                          --subs output/subs/reel_01.srt \
                          --out output/final/reel_01.mp4
"""
import argparse
import subprocess
from pathlib import Path

# Style des sous-titres brulés dans l'image (police, taille, contour, position)
SUBTITLE_STYLE = (
    "FontName=Arial Black,FontSize=14,PrimaryColour=&H00FFFFFF,"
    "OutlineColour=&H00000000,BorderStyle=1,Outline=2,Shadow=0,"
    "Alignment=2,MarginV=80"
)


def assemble(video_path: Path, audio_path: Path, subs_path: Path, out_path: Path):
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # subtitles filter exige un chemin echappe correctement sous ffmpeg
    subs_escaped = str(subs_path).replace(":", r"\:")

    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-i", str(audio_path),
        "-vf", f"subtitles='{subs_escaped}':force_style='{SUBTITLE_STYLE}'",
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        "-movflags", "+faststart",  # important pour la lecture instantanee sur mobile
        str(out_path),
    ]
    subprocess.run(cmd, check=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", type=str, required=True)
    parser.add_argument("--audio", type=str, required=True)
    parser.add_argument("--subs", type=str, required=True)
    parser.add_argument("--out", type=str, required=True)
    args = parser.parse_args()

    assemble(Path(args.video), Path(args.audio), Path(args.subs), Path(args.out))
    print(f"OK -> {args.out}")


if __name__ == "__main__":
    main()
