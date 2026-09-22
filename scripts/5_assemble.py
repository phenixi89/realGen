"""
Assemble video demo + voix off + sous-titres karaoke burn-in en un MP4 final
pret pour TikTok/Reels : vignette, fondus d'ouverture/fermeture et watermark
de marque, en plus du montage brut audio+video+sous-titres.

Usage:
    python 5_assemble.py --video output/video/demo_raw.webm \
                          --audio output/audio/reel_01.mp3 \
                          --subs output/subs/reel_01.ass \
                          --out output/final/reel_01.mp4
"""
import argparse
import re
import subprocess
from pathlib import Path

# Police du watermark. Chemin standard Debian/Ubuntu du paquet
# fonts-dejavu-core (installe dans l'image Docker du pipeline).
WATERMARK_FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

FADE_DURATION = 0.4

DURATION_RE = re.compile(r"Duration: (\d+):(\d+):(\d+\.\d+)")


def probe_duration(path: Path) -> float:
    # ffmpeg seul (pas ffprobe) : evite de devoir garantir la presence des
    # deux binaires -- `ffmpeg -i` sans sortie ecrit toujours la duree sur
    # stderr, meme sans -show_entries dedie.
    result = subprocess.run(
        ["ffmpeg", "-i", str(path)], capture_output=True, text=True,
    )
    match = DURATION_RE.search(result.stderr)
    if not match:
        raise RuntimeError(f"Impossible de lire la duree de {path}:\n{result.stderr}")
    h, m, s = match.groups()
    return int(h) * 3600 + int(m) * 60 + float(s)


def assemble(video_path: Path, audio_path: Path, subs_path: Path, out_path: Path):
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Le style (police, surlignage karaoke par mot) est deja embarque dans le
    # .ass genere par 4_generate_subtitles.py -- plus de force_style ici.
    subs_escaped = str(subs_path).replace(":", r"\:")
    duration = probe_duration(audio_path)
    fade_out_start = max(duration - FADE_DURATION, 0)

    vf = (
        f"subtitles='{subs_escaped}',"
        # Vignette legere : assombrit doucement les bords, evite le look
        # "capture d'ecran brute" plaquee telle quelle.
        f"vignette=PI/6,"
        f"drawtext=fontfile={WATERMARK_FONT}:text='OpusCV':"
        f"fontcolor=white@0.6:fontsize=34:x=40:y=40,"
        f"fade=t=in:st=0:d={FADE_DURATION},"
        f"fade=t=out:st={fade_out_start}:d={FADE_DURATION}"
    )
    af = (
        f"afade=t=in:st=0:d={FADE_DURATION},"
        f"afade=t=out:st={fade_out_start}:d={FADE_DURATION}"
    )

    cmd = [
        "ffmpeg", "-y",
        # La demo Playwright (souvent ~10s) est plus courte que la voix off
        # (15-20s) : sans boucler la video, -shortest tronquait l'audio (et
        # les sous-titres) a la duree de la video. En bouclant indefiniment
        # la video, c'est l'audio -- desormais le flux le plus court -- qui
        # fixe la duree finale ; la video se repete pour combler le reste.
        "-stream_loop", "-1", "-i", str(video_path),
        "-i", str(audio_path),
        "-vf", vf,
        "-af", af,
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
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
    parser.add_argument("--force", action="store_true",
                         help="Reassemble meme si --out existe deja")
    args = parser.parse_args()

    if not args.force and Path(args.out).exists():
        print(f"REPRISE: {args.out} existe deja, on saute (--force pour reassembler)")
        return

    assemble(Path(args.video), Path(args.audio), Path(args.subs), Path(args.out))
    print(f"OK -> {args.out}")


if __name__ == "__main__":
    main()
