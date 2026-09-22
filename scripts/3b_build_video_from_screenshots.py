"""
Transforme une serie de captures d'ecran (mode --mode screenshots de
3_record_demo.py) en une video muette avec effet de zoom in/out (Ken Burns),
consommable par 5_assemble.py exactement comme la video Playwright classique.

Chaque image devient un clip de --clip-seconds avec un zoom progressif
(ffmpeg zoompan), puis tous les clips sont concatenes.

Usage:
    python 3b_build_video_from_screenshots.py --screens output/video/reel_01 \
                                                --out output/video/reel_01/zoom.mp4
"""
import argparse
import subprocess
import tempfile
from pathlib import Path

FPS = 25
OUT_SIZE = (1080, 1920)


def build_clip(image_path: Path, clip_path: Path, seconds: float, zoom_out: bool):
    frames = int(seconds * FPS)
    # Zoom alterne in/out d'une image a l'autre pour eviter un mouvement
    # repetitif identique sur tout l'assemblage.
    if zoom_out:
        z_expr = f"if(eq(on,1),1.18,max(zoom-0.0015,1.0))"
    else:
        z_expr = f"min(zoom+0.0015,1.18)"

    vf = (
        # Les captures desktop (mode screenshots) sont en paysage (1440x900) ;
        # le format de sortie est vertical (9:16). scale+crop "cover" d'abord
        # pour remplir tout le cadre 1080x1920 sans bande blanche (recadre
        # le paysage sur sa partie centrale) -- sans cette etape, zoompan
        # partait d'une image bien plus large que haute et laissait la moitie
        # basse du cadre vide.
        f"scale=-2:{OUT_SIZE[1] * 3}:force_original_aspect_ratio=increase,"
        f"crop={OUT_SIZE[0] * 3}:{OUT_SIZE[1] * 3},"
        # x/y : formule centree standard de zoompan -- utilise ow/oh (taille
        # de sortie), pas iw/ih (taille source), sinon le cadrage part du
        # coin haut-gauche au lieu du centre a zoom=1.
        f"zoompan=z='{z_expr}':d={frames}:s={OUT_SIZE[0]}x{OUT_SIZE[1]}:"
        f"x='iw/2-(ow/zoom/2)':y='ih/2-(oh/zoom/2)':fps={FPS},"
        f"format=yuv420p"
    )
    cmd = [
        "ffmpeg", "-y", "-loop", "1", "-i", str(image_path),
        "-vf", vf, "-t", str(seconds),
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        str(clip_path),
    ]
    subprocess.run(cmd, check=True)


def build_video_from_screenshots(screens_dir: Path, out_path: Path, clip_seconds: float = 3.5):
    images = sorted(screens_dir.glob("*.png"))
    if not images:
        raise FileNotFoundError(f"Aucune capture .png dans {screens_dir}")

    out_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        clip_paths = []
        for i, image_path in enumerate(images):
            clip_path = tmp_dir / f"clip_{i:02d}.mp4"
            build_clip(image_path, clip_path, clip_seconds, zoom_out=(i % 2 == 1))
            clip_paths.append(clip_path)

        concat_list = tmp_dir / "concat.txt"
        concat_list.write_text(
            "\n".join(f"file '{p.as_posix()}'" for p in clip_paths), encoding="utf-8"
        )

        cmd = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list),
            "-c", "copy", str(out_path),
        ]
        subprocess.run(cmd, check=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--screens", type=str, required=True, help="Dossier contenant les .png")
    parser.add_argument("--out", type=str, required=True)
    parser.add_argument("--clip-seconds", type=float, default=3.5,
                         help="Duree du zoom sur chaque capture")
    parser.add_argument("--force", action="store_true",
                         help="Reconstruit meme si --out existe deja")
    args = parser.parse_args()

    out_path = Path(args.out)
    if not args.force and out_path.exists():
        print(f"REPRISE: {out_path} existe deja, on saute (--force pour reconstruire)")
        return

    build_video_from_screenshots(Path(args.screens), out_path, args.clip_seconds)
    print(f"OK -> {out_path}")


if __name__ == "__main__":
    main()
