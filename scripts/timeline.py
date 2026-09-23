"""
Montage cale sur la voix, partage par 3b (captures fixes) et 3c (video desktop).

timeline.json (ecrit par 4_generate_subtitles.py --timeline-out) dit quand
chaque scene du scenario est dite dans l'audio :
    {"duration": 29.8, "scenes": [{"feature": "checklist", "start": 3.1, "end": 7.4, ...}, ...]}

plan_items() associe a chaque scene les captures de SA fonctionnalite (dans
l'ordre du scenario, quel que soit l'ordre de capture) et leur repartit
exactement sa duree ; concat_with_xfade() recolle les clips pour que chaque
transition tombe pile au debut de la scene suivante.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

FPS = 25
XFADE_DURATION = 0.35
XFADE_TRANSITIONS = ["fade", "slideleft", "fade", "slideright", "smoothup"]
# En dessous, un plan n'a pas le temps d'etre lu : une scene courte montre
# moins de captures (les dernieres, qui montrent l'etat final de l'action).
MIN_ITEM_S = 1.2
MIN_SCENE_S = 0.1
TAIL_S = 0.2


def load_timeline(path: str | Path | None) -> dict | None:
    if not path:
        return None
    path = Path(path)
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def plan_items(timeline: dict, media_by_feature: dict[str, list],
               with_scene: bool = False) -> list[tuple]:
    """
    -> [(media, duree)] dans l'ordre d'affichage (with_scene : [(media,
    duree, index de la scene)]) ; la somme des durees vaut
    exactement la duree de l'audio. Fonctionnalite sans capture (selecteur
    casse, feature sautee) : on reprend les captures de la scene precedente,
    sinon l'apercu final, sinon n'importe quelle capture -- jamais d'ecran noir.
    """
    all_media = [m for items in media_by_feature.values() for m in items]
    if not all_media:
        raise ValueError("Aucune capture disponible pour le montage")

    plan = []
    previous = None
    for scene_index, scene in enumerate(timeline["scenes"]):
        duration = max(scene["end"] - scene["start"], MIN_SCENE_S)
        items = media_by_feature.get(scene.get("feature") or "")
        if not items:
            if scene.get("feature"):
                print(f"ATTENTION: aucune capture pour '{scene['feature']}', plan de secours", file=sys.stderr)
            items = previous or media_by_feature.get("apercu_cv") or all_media[-1:]
        count = max(1, min(len(items), int(duration / MIN_ITEM_S + 1e-6)))
        chosen = items[-count:]
        for media in chosen:
            plan.append((media, duration / count, scene_index) if with_scene else (media, duration / count))
        previous = items
    return plan


def clip_lengths(durations: list[float]) -> list[float]:
    """
    Chaque clip deborde de XFADE_DURATION sur le suivant : le fondu ne decale
    rien. Le dernier deborde de TAIL_S : une video plus courte que l'audio,
    meme de quelques ms (arrondis d'images), ferait boucler 5_assemble.py
    sur la premiere image.
    """
    return [d + (XFADE_DURATION if i < len(durations) - 1 else TAIL_S) for i, d in enumerate(durations)]


def concat_with_xfade(clip_paths: list[Path], durations: list[float], out_path: Path):
    """
    Clip i (de longueur clip_lengths()[i]) commence a sum(durations[:i]) :
    la transition i demarre exactement au debut de la scene/plan i.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if len(clip_paths) == 1:
        shutil.copy(clip_paths[0], out_path)
        return

    inputs = []
    for p in clip_paths:
        inputs += ["-i", str(p)]
    parts = []
    prev = "0:v"
    offset = 0.0
    for i in range(1, len(clip_paths)):
        offset += durations[i - 1]
        transition = XFADE_TRANSITIONS[(i - 1) % len(XFADE_TRANSITIONS)]
        parts.append(f"[{prev}][{i}:v]xfade=transition={transition}:"
                     f"duration={XFADE_DURATION}:offset={offset:.3f}[v{i}]")
        prev = f"v{i}"
    parts.append(f"[{prev}]format=yuv420p[vout]")
    subprocess.run([
        "ffmpeg", "-y", "-loglevel", "error", *inputs,
        "-filter_complex", ";".join(parts), "-map", "[vout]", "-r", str(FPS),
        "-c:v", "libx264", "-preset", "medium", "-crf", "18", str(out_path),
    ], check=True)
