"""
Transforme une serie de captures d'ecran (mode --mode screenshots de
3_record_demo.py) en une video muette avec effet de zoom in/out (Ken Burns),
consommable par 5_assemble.py exactement comme la video Playwright classique.

Chaque image devient un clip de --clip-seconds avec un zoom progressif
(ffmpeg zoompan), les clips s'enchainent ensuite en fondus (xfade) au lieu
de coupes franches -- un montage a la coupe entre des captures fixes se
voit immediatement comme un diaporama, pas une video.

Usage:
    python 3b_build_video_from_screenshots.py --screens output/video/reel_01 \
                                                --out output/video/reel_01/zoom.mp4
"""
import argparse
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image

import catalog
from scene_compose import frame_scene
from render_js_anim import file_uri, parse_spec, render_clip, render_frames
from timeline import clip_lengths, concat_with_xfade, load_timeline, plan_items

FPS = 25
OUT_SIZE = (1080, 1920)
XFADE_DURATION = 0.5
# Alterne quelques transitions xfade standard (toutes supportees nativement
# par ffmpeg) pour eviter que l'assemblage entier ait le meme fondu repete.
XFADE_TRANSITIONS = ["fade", "slideleft", "fade", "slideright"]
ZOOM_STEP = 0.0015
ZOOM_MAX = 1.18
# Le souligne attend la fin du fondu d'entree du clip (timeline.XFADE_DURATION).
HIGHLIGHT_DELAY_S = 0.45
CURSOR_CLICK_AT = 1.0  # assets/anim/cursor.html CLICK_AT
# Annotation au feutre (assets/anim/annotation.html) : apres le fondu d'entree,
# ou juste apres le clic quand le curseur anime est sur le meme plan.
ANNOTATION_DELAY_S = 0.45
ANNOTATION_AFTER_CLICK_S = 0.3
ANNOTATION_MIN_VISIBLE_S = 1.3


def build_clip(image_path: Path, clip_path: Path, seconds: float, zoom_out: bool,
               overlay_frames: Path | list[Path] | None = None, focus: tuple[float, float] | None = None):
    """
    focus : point vise par le zoom (fractions du cadre, captures.json "focus"),
    sinon le centre. overlay_frames : dossier(s) de PNG transparents (souligne,
    curseur, annotation... cf. render_js_anim.py) incrustes par-dessus le zoom,
    image par image, dans l'ordre de la liste.
    """
    frames = int(seconds * FPS)
    fx, fy = focus or (0.5, 0.5)
    # Zoom alterne in/out d'une image a l'autre pour eviter un mouvement
    # repetitif identique sur tout l'assemblage. Modifier ces expressions ?
    # assets/anim/highlight.html (zoomAt) les reproduit pour suivre la carte.
    if zoom_out:
        z_expr = f"if(eq(on,1),{ZOOM_MAX},max(zoom-{ZOOM_STEP},1.0))"
    else:
        z_expr = f"min(zoom+{ZOOM_STEP},{ZOOM_MAX})"

    vf = (
        # Les captures desktop (mode screenshots) sont en paysage (1440x900) ;
        # le format de sortie est vertical (9:16). scale+crop "cover" d'abord
        # pour remplir tout le cadre 1080x1920 sans bande blanche (recadre
        # le paysage sur sa partie centrale) -- sans cette etape, zoompan
        # partait d'une image bien plus large que haute et laissait la moitie
        # basse du cadre vide.
        f"scale=-2:{OUT_SIZE[1] * 3}:force_original_aspect_ratio=increase,"
        f"crop={OUT_SIZE[0] * 3}:{OUT_SIZE[1] * 3},"
        # x/y : zoom centre -- la fenetre visible fait iw/zoom de large (en
        # pixels SOURCE). Avec ow/oh (taille de sortie, 3x plus petite ici),
        # x/y depassaient la borne max et zoompan les ramenait au bord :
        # le zoom partait vers le coin bas-droit au lieu du centre.
        f"zoompan=z='{z_expr}':d={frames}:s={OUT_SIZE[0]}x{OUT_SIZE[1]}:"
        # Zoom cible (focus) : fenetre centree sur le point, clampee au cadre
        # -- meme calcul que common.js zoomCss pour les surimpressions.
        f"x='max(0,min(iw-iw/zoom,iw*{fx:.4f}-iw/zoom/2))':"
        f"y='max(0,min(ih-ih/zoom,ih*{fy:.4f}-ih/zoom/2))':fps={FPS}"
    )
    inputs = ["-loop", "1", "-i", str(image_path)]
    layers = [overlay_frames] if isinstance(overlay_frames, Path) else list(overlay_frames or [])
    if layers:
        chain = [f"[0:v]{vf}[l0]"]
        for k, frames_dir in enumerate(layers, 1):
            inputs += ["-framerate", str(FPS), "-i", str(frames_dir / "%05d.png")]
            chain.append(f"[l{k - 1}][{k}:v]overlay=eof_action=pass" + (",format=yuv420p[v]" if k == len(layers) else f"[l{k}]"))
        filters = ["-filter_complex", ";".join(chain), "-map", "[v]"]
    else:
        filters = ["-vf", f"{vf},format=yuv420p"]
    cmd = [
        "ffmpeg", "-y", *inputs, *filters, "-t", str(seconds),
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

        if len(clip_paths) == 1:
            shutil.copy(clip_paths[0], out_path)
            return

        inputs = []
        for p in clip_paths:
            inputs += ["-i", str(p)]

        # Chaine de xfade : chaque transition demarre "offset" secondes dans
        # le flux cumule precedent (proche de sa fin), et le resultat perd
        # xfade_duration a chaque jointure (les deux clips se chevauchent
        # brievement au lieu de se succeder).
        filter_parts = []
        cum_duration = clip_seconds
        prev_label = "0:v"
        for i in range(1, len(clip_paths)):
            transition = XFADE_TRANSITIONS[(i - 1) % len(XFADE_TRANSITIONS)]
            offset = max(cum_duration - XFADE_DURATION, 0)
            out_label = f"v{i}"
            filter_parts.append(
                f"[{prev_label}][{i}:v]xfade=transition={transition}:"
                f"duration={XFADE_DURATION}:offset={offset:.3f}[{out_label}]"
            )
            prev_label = out_label
            cum_duration = cum_duration + clip_seconds - XFADE_DURATION

        cmd = [
            "ffmpeg", "-y", *inputs,
            "-filter_complex", ";".join(filter_parts),
            "-map", f"[{prev_label}]",
            "-c:v", "libx264", "-preset", "medium", "-crf", "18",
            str(out_path),
        ]
        subprocess.run(cmd, check=True)


def build_video_on_timeline(screens_dir: Path, out_path: Path, timeline: dict,
                            scene_anims: dict[int, str] | None = None, highlight: bool = False,
                            highlight_skip: set[int] | None = None, theme: dict | None = None,
                            cursor: bool = False, cursor_scenes: set[int] | None = None,
                            annotations: dict[int, str] | None = None) -> dict[str, list[float]]:
    """
    Montage cale sur la voix : chaque scene du scenario affiche les captures
    de SA fonctionnalite (captures.json, ecrit par 3_record_demo.py) pendant
    exactement le temps ou la voix en parle (timeline.json).

    scene_anims : {index de scene (negatif = depuis la fin): "gabarit?params"}
    -- ces scenes montrent un plan anime plein cadre (assets/anim/) a la place
    de leurs captures ; sans ?bg=, le fond est la derniere capture qu'elles
    auraient montree. highlight : cadre anime autour de la carte nette de la
    premiere capture de chaque scene (captures.json "card"), sauf les
    scenes de highlight_skip (ex: celles qui ont une surimpression).
    theme : couleurs/polices des animations (catalog/themes.json).
    cursor : curseur anime qui clique sur le bouton d'action (captures.json
    "focus") ; avec highlight, les deux alternent d'une scene a l'autre.
    cursor_scenes : scenes qui ont le curseur meme sans cursor (scene "preuve").
    annotations : {index de scene: texte du post-it ("" = cercle seul)} -- la
    derniere capture de la scene est annotee au feutre (bouton "focus" entoure,
    sinon la carte nette), apres le clic du curseur s'il est sur le meme plan.
    Chaque capture avec "focus" est zoomee vers ce point.
    -> {"clics": instants des clics du curseur, "feutre": debuts des annotations}
       (effets sonores, cf. run_pipeline.py).
    """
    clicks: list[float] = []
    strokes: list[float] = []
    theme_params = catalog.anim_params(theme)
    captures = json.loads((screens_dir / "captures.json").read_text(encoding="utf-8"))
    media_by_feature: dict[str, list[Path]] = {}
    card_by_file: dict[str, list[int]] = {}
    focus_by_file: dict[str, list[int]] = {}
    for shot in captures:
        media_by_feature.setdefault(shot["feature"], []).append(screens_dir / shot["file"])
        if shot.get("card"):
            card_by_file[shot["file"]] = shot["card"]
        if shot.get("focus"):
            focus_by_file[shot["file"]] = shot["focus"]
    if highlight and not card_by_file:
        print("ATTENTION: captures.json sans position de carte (captures anterieures a --anims highlight) "
              "-> pas de souligne ; relancer la capture (--from-step video) pour l'activer")

    # Scene animee : feature remplacee par une cle a part, dont l'unique
    # "media" est la spec d'animation -- plan_items() lui donne alors toute
    # la duree de la scene, et le reste du montage (xfade) ne change pas.
    timeline = {**timeline, "scenes": [dict(sc) for sc in timeline["scenes"]]}
    all_media = [m for items in media_by_feature.values() for m in items]
    for index, spec in (scene_anims or {}).items():
        if not -len(timeline["scenes"]) <= index < len(timeline["scenes"]):
            print(f"ATTENTION: scene {index} inexistante ({len(timeline['scenes'])} scenes), animation ignoree")
            continue
        scene = timeline["scenes"][index]
        name, params = parse_spec(spec)
        if "bg" not in params:
            own = media_by_feature.get(scene.get("feature") or "") or all_media[-1:]
            if own:
                params["bg"] = file_uri(own[-1])
        key = f"__anim_{index % len(timeline['scenes'])}"
        media_by_feature[key] = [(name, params)]
        scene["feature"] = key

    plan = plan_items(timeline, media_by_feature, with_scene=True)
    durations = [d for _, d, _ in plan]
    with tempfile.TemporaryDirectory() as tmp:
        clips = []
        previous_scene = None
        for i, ((media, _, scene_index), length) in enumerate(zip(plan, clip_lengths(durations))):
            clip = Path(tmp) / f"clip_{i:02d}.mp4"
            zoom_out = i % 2 == 1
            if isinstance(media, tuple):
                name, params = media
                print(f"Scene {scene_index} : animation '{name}' ({length:.1f}s)")
                render_clip(name, {**theme_params, **params}, clip, length)
            else:
                card = card_by_file.get(media.name)
                focus = focus_by_file.get(media.name)
                fxy = (focus[0] / OUT_SIZE[0], focus[1] / OUT_SIZE[1]) if focus else None
                zoom_params = {"zoom": "out" if zoom_out else "in", "step": ZOOM_STEP, "zmax": ZOOM_MAX,
                               "fps": FPS, "fx": (fxy or (0.5, 0.5))[0], "fy": (fxy or (0.5, 0.5))[1]}
                first_of_scene = scene_index != previous_scene and scene_index not in (highlight_skip or set())
                # Curseur si possible ; avec le souligne aussi actif, une scene sur deux.
                use_cursor = focus and first_of_scene and (
                    (cursor and (not highlight or scene_index % 2 == 0)) or scene_index in (cursor_scenes or set()))
                # Annotation sur la DERNIERE capture de la scene (l'ecran de resultat, apres
                # le clic du curseur sur la premiere) ; scene d'une seule capture : apres le clic.
                last_of_scene = i == len(plan) - 1 or plan[i + 1][2] != scene_index
                annotate = last_of_scene and scene_index in (annotations or {}) and bool(focus or card)
                overlay = []
                if use_cursor:
                    overlay.append(Path(tmp) / f"cur_{i:02d}")
                    render_frames("cursor", {**theme_params, **zoom_params, "x": focus[0], "y": focus[1],
                                             "delay": HIGHLIGHT_DELAY_S}, overlay[-1])
                    clicks.append(sum(durations[:i]) + HIGHLIGHT_DELAY_S + CURSOR_CLICK_AT)
                elif highlight and card and first_of_scene and not annotate:
                    overlay.append(Path(tmp) / f"hl_{i:02d}")
                    x, y, w, h = card
                    render_frames("highlight", {**theme_params, **zoom_params, "x": x, "y": y, "w": w, "h": h,
                                                "delay": HIGHLIGHT_DELAY_S}, overlay[-1])
                if annotate:
                    delay = annotation_delay(length, bool(use_cursor))
                    strokes.append(sum(durations[:i]) + delay)
                    target = {"x": focus[0], "y": focus[1]} if focus else dict(zip(("rx", "ry", "rw", "rh"), card))
                    overlay.append(Path(tmp) / f"ann_{i:02d}")
                    print(f"Scene {scene_index} : annotation au feutre ({annotations[scene_index] or 'cercle seul'})")
                    # Rendu sur toute la duree du plan : l'annotation reste jusqu'au fondu suivant.
                    render_frames("annotation", {**theme_params, **zoom_params, **target, "delay": f"{delay:.2f}",
                                                 "texte": annotations[scene_index], "pen": 0 if use_cursor else 1},
                                  overlay[-1], duration=length)
                source = media
                if card and theme and theme.get("cadre", "navigateur") == "navigateur":
                    # Habillage du theme (fond + fenetre de navigateur), carte a la meme place.
                    source = Path(tmp) / f"framed_{i:02d}.png"
                    frame_scene(Image.open(media), card, theme, seed=i).save(source)
                build_clip(source, clip, length, zoom_out=zoom_out, overlay_frames=overlay, focus=fxy)
            previous_scene = scene_index
            clips.append(clip)
        concat_with_xfade(clips, durations, out_path, (theme or {}).get("transitions"))
    return {"clics": clicks, "feutre": strokes}


def annotation_delay(clip_length: float, after_cursor: bool) -> float:
    """Debut du trace (s, dans le plan) ; garde au moins ANNOTATION_MIN_VISIBLE_S d'annotation finie."""
    wanted = HIGHLIGHT_DELAY_S + CURSOR_CLICK_AT + ANNOTATION_AFTER_CLICK_S if after_cursor else ANNOTATION_DELAY_S
    return max(0.2, min(wanted, clip_length - ANNOTATION_MIN_VISIBLE_S))


def parse_annotations(values: list[str]) -> dict[int, str]:
    """["3=Clique ici", "5="] -> {3: "Clique ici", 5: ""}"""
    out = {}
    for value in values:
        index, sep, text = value.partition("=")
        if not sep:
            raise ValueError(f"--annotate attend INDEX=texte, recu '{value}'")
        out[int(index)] = text.strip()
    return out


def parse_scene_anims(values: list[str]) -> dict[int, str]:
    """["-1=cta?title=...", "0=cta"] -> {-1: "cta?title=...", 0: "cta"}"""
    anims = {}
    for value in values:
        index, sep, spec = value.partition("=")
        if not sep or not spec:
            raise ValueError(f"--scene-anim attend INDEX=gabarit[?params], recu '{value}'")
        anims[int(index)] = spec
    return anims


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--screens", type=str, required=True, help="Dossier contenant les .png")
    parser.add_argument("--out", type=str, required=True)
    parser.add_argument("--timeline", type=str, default=None,
                         help="timeline.json (4_generate_subtitles.py) : cale chaque scene sur la voix. "
                              "Absent -> ancien montage, captures a duree fixe dans l'ordre de capture")
    parser.add_argument("--clip-seconds", type=float, default=3.5,
                         help="Duree du zoom sur chaque capture (sans timeline uniquement)")
    parser.add_argument("--scene-anim", action="append", default=[], metavar="INDEX=GABARIT[?PARAMS]",
                         help="Remplace les captures d'une scene par une animation plein cadre "
                              "(assets/anim/), ex: -1=cta ; repetable (avec --timeline)")
    parser.add_argument("--highlight", action="store_true",
                         help="Cadre anime autour de la zone montree, au debut de chaque scene (avec --timeline)")
    parser.add_argument("--theme", type=str, default=None, help="Theme visuel des animations (catalog/themes.json)")
    parser.add_argument("--cursor", action="store_true",
                         help="Curseur anime qui clique sur le bouton d'action des captures (avec --timeline)")
    parser.add_argument("--cursor-scene", action="append", type=int, default=[], metavar="INDEX",
                         help="Curseur anime sur cette scene meme sans --cursor (scene preuve) ; repetable")
    parser.add_argument("--annotate", action="append", default=[], metavar="INDEX=TEXTE",
                         help="Annotation au feutre sur la derniere capture de la scene INDEX (cercle + post-it TEXTE, "
                              "vide = cercle seul) ; repetable (avec --timeline)")
    parser.add_argument("--highlight-skip", action="append", type=int, default=[], metavar="INDEX",
                         help="Scene sans cadre anime (--highlight) ; repetable")
    parser.add_argument("--force", action="store_true",
                         help="Reconstruit meme si --out existe deja")
    args = parser.parse_args()

    out_path = Path(args.out)
    if not args.force and out_path.exists():
        print(f"REPRISE: {out_path} existe deja, on saute (--force pour reconstruire)")
        return

    screens_dir = Path(args.screens)
    timeline = load_timeline(args.timeline)
    if timeline and (screens_dir / "captures.json").exists():
        events = build_video_on_timeline(screens_dir, out_path, timeline, cursor=args.cursor,
                                scene_anims=parse_scene_anims(args.scene_anim), highlight=args.highlight,
                                highlight_skip=set(args.highlight_skip), cursor_scenes=set(args.cursor_scene),
                                annotations=parse_annotations(args.annotate),
                                theme=catalog.get_theme(args.theme) if args.theme else None)
        # Instants des clics du curseur et des annotations, pour les effets sonores (run_pipeline.py -> 5_assemble.py).
        out_path.with_suffix(".events.json").write_text(json.dumps(events), encoding="utf-8")
    else:
        build_video_from_screenshots(screens_dir, out_path, args.clip_seconds)
    print(f"OK -> {out_path}")


if __name__ == "__main__":
    main()
