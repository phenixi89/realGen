"""
Transforme l'enregistrement continu du mode --mode video_desktop de
3_record_demo.py (raw.webm + segments.json) en une video muette recadree
sur, a chaque instant, l'element de la fonctionnalite en train d'etre montree
-- pas le viewport desktop entier (1440x900, avec tout l'environnement
autour). Consommable ensuite par 5_assemble.py exactement comme la video
Playwright mobile ou le montage --mode screenshots.

segments.json (ecrit par 3_record_demo.py) :
{
  "device_scale_factor": 2,
  "video_size": {"width": 2880, "height": 1800},
  "segments": [
    {"name": "mes_cvs", "start": 0.0, "end": 1.8, "bbox": {"x":.., "y":.., "width":.., "height":..}},
    ...
  ]
}
bbox est en pixels CSS (coordonnees Playwright bounding_box()) ; "video_size"
est deja a l'echelle device_scale_factor -- d'ou le *scale ci-dessous pour
retomber sur les pixels reels de la video.

Usage:
    python 3c_build_video_from_recording.py --dir output/video/reel_01 \
                                              --out output/video/reel_01/zoom.mp4
"""
import argparse
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

OUT_SIZE = (1080, 1920)
OUT_RATIO = OUT_SIZE[0] / OUT_SIZE[1]
XFADE_DURATION = 0.4
XFADE_TRANSITIONS = ["fade", "slideleft", "fade", "slideright"]
# Marge autour de l'element vise : trop serre, un recadrage anime au montage
# (5_assemble.py) ou un leger decalage de bbox sortirait du cadre.
PAD_RATIO = 0.18
MIN_SEGMENT_DURATION = 0.25


def _compute_crop_box(bbox: dict | None, video_w: int, video_h: int, scale: float) -> tuple[int, int, int, int]:
    """
    Calcule (x, y, w, h) en pixels video a recadrer autour de bbox, en forcant
    le ratio 9:16 (agrandit la plus petite dimension plutot que de deformer),
    et en recalant le cadre pour rester dans les limites de la frame plutot
    que de deborder. bbox absent (element non mesurable) -> plein cadre
    recentre (fallback "cover", comme un plan large plutot qu'un echec).
    """
    if bbox is None:
        box_h = video_h
        box_w = box_h * OUT_RATIO
        if box_w > video_w:
            box_w = video_w
            box_h = box_w / OUT_RATIO
        return int((video_w - box_w) / 2), int((video_h - box_h) / 2), int(box_w), int(box_h)

    x = bbox["x"] * scale
    y = bbox["y"] * scale
    w = bbox["width"] * scale
    h = bbox["height"] * scale

    box_w = w * (1 + 2 * PAD_RATIO)
    box_h = h * (1 + 2 * PAD_RATIO)
    if box_w / box_h > OUT_RATIO:
        box_h = box_w / OUT_RATIO
    else:
        box_w = box_h * OUT_RATIO

    # Reduit les deux dimensions ensemble (meme facteur) si besoin -- les
    # clamper independamment casserait le ratio 9:16 tout juste impose
    # ci-dessus.
    shrink = min(video_w / box_w, video_h / box_h, 1.0)
    box_w *= shrink
    box_h *= shrink

    cx, cy = x + w / 2, y + h / 2
    crop_x = max(0, min(cx - box_w / 2, video_w - box_w))
    crop_y = max(0, min(cy - box_h / 2, video_h - box_h))
    return int(crop_x), int(crop_y), int(box_w), int(box_h)


def _extract_segment(raw_path: Path, clip_path: Path, start: float, end: float, crop_box: tuple[int, int, int, int]):
    x, y, w, h = crop_box
    duration = max(end - start, MIN_SEGMENT_DURATION)
    vf = f"crop={w}:{h}:{x}:{y},scale={OUT_SIZE[0]}:{OUT_SIZE[1]},format=yuv420p"
    cmd = [
        "ffmpeg", "-y", "-ss", f"{start:.3f}", "-i", str(raw_path),
        "-t", f"{duration:.3f}", "-vf", vf, "-an",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        str(clip_path),
    ]
    subprocess.run(cmd, check=True)


def build_video_from_recording(recording_dir: Path, out_path: Path):
    raw_path = recording_dir / "raw.webm"
    manifest = json.loads((recording_dir / "segments.json").read_text(encoding="utf-8"))
    if not raw_path.exists():
        raise FileNotFoundError(f"{raw_path} introuvable")

    scale = manifest["device_scale_factor"]
    video_w, video_h = manifest["video_size"]["width"], manifest["video_size"]["height"]
    segments = manifest["segments"]
    if not segments:
        raise ValueError(f"Aucun segment dans {recording_dir / 'segments.json'}")

    out_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        clip_paths = []
        clip_durations = []
        for i, seg in enumerate(segments):
            crop_box = _compute_crop_box(seg.get("bbox"), video_w, video_h, scale)
            clip_path = tmp_dir / f"clip_{i:02d}.mp4"
            duration = max(seg["end"] - seg["start"], MIN_SEGMENT_DURATION)
            _extract_segment(raw_path, clip_path, seg["start"], seg["end"], crop_box)
            clip_paths.append(clip_path)
            clip_durations.append(duration)

        if len(clip_paths) == 1:
            shutil.copy(clip_paths[0], out_path)
            return

        inputs = []
        for p in clip_paths:
            inputs += ["-i", str(p)]

        # Meme chaine xfade que 3b_build_video_from_screenshots.py : chaque
        # transition demarre pres de la fin du flux cumule precedent, les
        # clips se chevauchent brievement au lieu de se succeder a la coupe.
        filter_parts = []
        cum_duration = clip_durations[0]
        prev_label = "0:v"
        for i in range(1, len(clip_paths)):
            transition = XFADE_TRANSITIONS[(i - 1) % len(XFADE_TRANSITIONS)]
            fade_dur = min(XFADE_DURATION, clip_durations[i - 1], clip_durations[i]) or 0.05
            offset = max(cum_duration - fade_dur, 0)
            out_label = f"v{i}"
            filter_parts.append(
                f"[{prev_label}][{i}:v]xfade=transition={transition}:"
                f"duration={fade_dur:.3f}:offset={offset:.3f}[{out_label}]"
            )
            prev_label = out_label
            cum_duration = cum_duration + clip_durations[i] - fade_dur

        cmd = [
            "ffmpeg", "-y", *inputs,
            "-filter_complex", ";".join(filter_parts),
            "-map", f"[{prev_label}]",
            "-c:v", "libx264", "-preset", "medium", "-crf", "18",
            str(out_path),
        ]
        subprocess.run(cmd, check=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", type=str, required=True,
                         help="Dossier contenant raw.webm + segments.json (--mode video_desktop)")
    parser.add_argument("--out", type=str, required=True)
    parser.add_argument("--force", action="store_true",
                         help="Reconstruit meme si --out existe deja")
    args = parser.parse_args()

    out_path = Path(args.out)
    if not args.force and out_path.exists():
        print(f"REPRISE: {out_path} existe deja, on saute (--force pour reconstruire)")
        return

    build_video_from_recording(Path(args.dir), out_path)
    print(f"OK -> {out_path}")


if __name__ == "__main__":
    main()
