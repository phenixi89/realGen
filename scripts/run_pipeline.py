"""
Orchestrateur : enchaine script -> voix -> demo -> sous-titres -> assemblage
pour generer N reels en une seule commande.

Usage:
    python run_pipeline.py --n 3 --saas-url https://tonapp.com --voice Kore
"""
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlencode

from script_text import script_to_text

ROOT = Path(__file__).parent

# Ordre des etapes : forcer une etape force aussi celles d'apres, sinon un
# sous-titre/assemblage "REPRISE" resterait construit sur une video ou un
# audio perimes.
STEPS = ["script", "voice", "video", "subs", "assemble"]


# Animations HTML/JS (assets/anim/, rendues par render_js_anim.py) :
#   overlay   -> surimpression sur une scene (5_assemble.py, tous modes)
#   scene     -> une scene devient un plan anime plein cadre (3b, screenshots)
#   highlight -> cadre anime autour de la zone montree (3b, screenshots)
ANIM_KINDS = ["overlay", "scene", "highlight"]
DEFAULT_OVERLAY = "score_ats"
DEFAULT_SCENE_ANIM = "cta"
CONSEIL_CTA = "cta?" + urlencode({"title": "Teste ton CV gratuitement", "sub": "Lien en bio · abonne-toi pour la suite",
                                  "button": "Essaie OpusCV"})
# Scene qui recoit la surimpression par defaut : la premiere qui parle de
# ces fonctionnalites (ATS/optimisation), sinon la 2e scene.
OVERLAY_FEATURES = ("checklist", "relecture", "adapter", "fonctions_ia")
# Laisse passer le fondu d'entree de la scene avant la surimpression.
OVERLAY_DELAY_S = 0.3
# Accroche d'ouverture : affichee pendant la 1re scene, dans ces bornes.
HOOK_MIN_S = 1.6
HOOK_MAX_S = 4.0


def parse_anims(value: str) -> list[str]:
    kinds = [k.strip() for k in value.split(",") if k.strip()]
    if kinds in (["none"], []):
        return []
    if kinds == ["all"]:
        return list(ANIM_KINDS)
    unknown = [k for k in kinds if k not in ANIM_KINDS]
    if unknown:
        raise argparse.ArgumentTypeError(f"animation(s) inconnue(s) {unknown} ; choix : {', '.join(ANIM_KINDS)}, all, none")
    return kinds


def anim_spec(value, default_template: str) -> str:
    """Champ de scene "anim"/"overlay" : true, "gabarit?params" ou {"template": ..., params}."""
    if isinstance(value, dict):
        params = {k: v for k, v in value.items() if k != "template"}
        template = value.get("template", default_template)
        return f"{template}?{urlencode(params)}" if params else template
    if isinstance(value, str):
        return value
    return default_template


def plan_montage(script: dict, timeline: dict, kinds: list[str], cards: bool,
                 hook: bool) -> tuple[list[str], list[str]]:
    """
    -> (arguments 3b, arguments 5_assemble) pour un reel.

    - cards : scenes "carte" du scenario (formats conseil) -> plans animes
      assets/anim/carte.html, toujours (independant de --anims) ;
    - kinds (--anims) : le scenario peut placer les animations lui-meme
      (champs "anim"/"overlay" d'une scene, cf. scenarios/exemple.json) ;
      sinon placement par defaut : CTA anime sur la derniere scene, score
      ATS sur la scene ATS/optimisation ;
    - hook : accroche_ecran en grand des la 1re image, pendant la 1re scene ;
    - theme du scenario transmis aux deux etapes.
    """
    scenes = [s for s in script.get("scenes", []) if s.get("texte", "").strip()]
    t_scenes = timeline["scenes"]
    if len(scenes) != len(t_scenes):
        scenes = [{}] * len(t_scenes)  # timeline sans scenario (ancien format) : placement par defaut
    video_args, assemble_args = [], []
    if script.get("theme"):
        video_args += ["--theme", script["theme"]]
        assemble_args += ["--theme", script["theme"]]

    card_scenes = {i for i, s in enumerate(scenes) if s.get("carte")} if cards else set()
    scene_anims = {i: "carte?" + urlencode(scenes[i]["carte"]) for i in card_scenes}
    last = len(t_scenes) - 1
    chosen = {i: anim_spec(s["anim"], DEFAULT_SCENE_ANIM) for i, s in enumerate(scenes) if s.get("anim")}
    # Fin de reel "conseil" : toujours un CTA anime plein cadre (une capture
    # de l'app n'y dit rien) ; pour les demos, seulement avec --anims scene.
    wants_cta = "scene" in kinds or (cards and script.get("categorie") == "conseil")
    if wants_cta and t_scenes and not chosen and last not in card_scenes:
        chosen = {last: CONSEIL_CTA if script.get("categorie") == "conseil" else DEFAULT_SCENE_ANIM}
    if "scene" in kinds or cards:
        scene_anims.update(chosen)
    for i, spec in sorted(scene_anims.items()):
        video_args += ["--scene-anim", f"{i}={spec}"]

    overlays = {}
    if "overlay" in kinds and t_scenes:
        overlays = {i: anim_spec(s["overlay"], DEFAULT_OVERLAY) for i, s in enumerate(scenes) if s.get("overlay")}
        if not overlays:
            # Jamais sur la 1re scene (accroche) ni sur un plan deja anime
            # (carte, CTA) : aucune scene libre -> pas de surimpression.
            free = [i for i in range(1, len(t_scenes)) if i not in scene_anims]
            default = next((i for i in free if t_scenes[i].get("feature") in OVERLAY_FEATURES), free[0] if free else None)
            overlays = {default: DEFAULT_OVERLAY} if default is not None else {}
        for i, spec in overlays.items():
            start = t_scenes[i]["start"] + OVERLAY_DELAY_S
            # fit : l'animation accelere si besoin pour finir avec sa scene.
            fit = max(t_scenes[i]["end"] - start, 1.0)
            spec += ("&" if "?" in spec else "?") + f"fit={fit:.2f}"
            assemble_args += ["--overlay", f"{start:.2f}:{spec}"]

    if "highlight" in kinds:
        video_args.append("--highlight")
        # Pas de cadre sous une surimpression : les deux se disputeraient l'ecran.
        for i in overlays:
            video_args += ["--highlight-skip", str(i)]

    if hook and script.get("accroche_ecran") and t_scenes:
        first_scene = t_scenes[0]["end"] - t_scenes[0]["start"]
        assemble_args += ["--hook-text", script["accroche_ecran"],
                          "--hook-duration", f"{min(max(first_scene, HOOK_MIN_S), HOOK_MAX_S):.2f}"]
    return video_args, assemble_args


def write_caption_file(script: dict, path: Path):
    """Texte de publication (legende + hashtags) a cote du reel final."""
    lines = [script.get("legende", "").strip(), "", " ".join(script.get("hashtags") or [])]
    path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def run(cmd: list[str]):
    print(f"\n$ {' '.join(cmd)}")
    result = subprocess.run(cmd)
    if result.returncode != 0:
        print(f"ECHEC de la commande: {' '.join(cmd)}", file=sys.stderr)
        sys.exit(result.returncode)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=3, help="Nombre de reels a generer")
    parser.add_argument("--saas-url", type=str, required=True, help="URL de demo de ton SaaS")
    parser.add_argument("--voice", type=str, default="Kore")
    parser.add_argument("--whisper-model", type=str, default="small")
    parser.add_argument("--capture-mode", type=str, default="video",
                         choices=["video", "screenshots", "video_desktop"],
                         help="video = enregistrement mobile continu ; "
                              "screenshots = captures desktop animees en zoom in/out au montage ; "
                              "video_desktop = enregistrement desktop continu, recadre ensuite sur "
                              "chaque fonctionnalite montree (mouvement reel, pas un zoom artificiel)")
    parser.add_argument("--duration", type=int, default=30, help="Duree cible de chaque reel, en secondes")
    parser.add_argument("--angle", type=str, default=None, help="Angle marketing impose pour les scenarios")
    parser.add_argument("--scenario", type=str, default=None,
                         help="Scenario(s) ecrit(s) a la main (JSON, voir scenarios/exemple.json) ; remplace --n")
    parser.add_argument("--force", action="store_true",
                         help="Ignore les sorties existantes et regenere tout depuis zero (equivalent a --from-step script)")
    parser.add_argument("--from-step", type=str, choices=STEPS, default=None,
                         help="Force la regeneration a partir de cette etape (et toutes celles d'apres) ; "
                              "les etapes precedentes restent en reprise si deja presentes")
    parser.add_argument("--anims", type=parse_anims, default=[],
                         help="Animations HTML/JS a integrer, separees par des virgules : "
                              "overlay (surimpression score ATS), scene (scene CTA animee), "
                              "highlight (cadre anime sur la zone montree) ; ou all / none (defaut). "
                              "scene/highlight : --capture-mode screenshots uniquement")
    parser.add_argument("--format", type=str, default=None,
                         help="Format impose (catalog/formats.json) ; sinon choix automatique (mix conseil/produit)")
    parser.add_argument("--theme", type=str, default=None,
                         help="Theme visuel impose (catalog/themes.json) ; sinon rotation")
    parser.add_argument("--hook", type=str, default=None,
                         help="Style d'accroche impose (catalog/hooks.json) ; sinon rotation")
    parser.add_argument("--no-hook-overlay", action="store_true",
                         help="N'affiche pas l'accroche en grand au debut de la video")
    args = parser.parse_args()

    screen_only = [k for k in args.anims if k in ("scene", "highlight")]
    if screen_only and args.capture_mode != "screenshots":
        print(f"ATTENTION: --anims {','.join(screen_only)} ne s'applique qu'en --capture-mode screenshots -> ignore")
        args.anims = [k for k in args.anims if k not in screen_only]

    out = Path("output")
    from_index = 0 if args.force else (STEPS.index(args.from_step) if args.from_step else None)

    # Un scenario/angle impose ou une duree differente de l'existant : les
    # sorties en cache ne correspondent plus a la demande -> tout regenerer,
    # sinon la reprise ressortirait silencieusement l'ancien reel.
    scripts_path = out / "scripts.json"
    if from_index is None and scripts_path.exists():
        existing = json.loads(scripts_path.read_text(encoding="utf-8"))
        stale_duration = any(s.get("duree_cible_s") != args.duration for s in existing) and not args.scenario
        stale_catalog = any(v and any(sc.get(k) != v for sc in existing)
                            for k, v in (("format", args.format), ("theme", args.theme), ("hook", args.hook)))
        if args.scenario or args.angle or stale_duration or stale_catalog:
            print("Parametres de scenario differents de la derniere execution -> regeneration complete")
            from_index = 0

    def force_flag_for(step: str) -> list[str]:
        return ["--force"] if from_index is not None and STEPS.index(step) >= from_index else []

    # Un dossier video garde le marqueur du --capture-mode qui l'a rempli :
    # video/screenshots/video_desktop produisent des fichiers de natures
    # differentes (*.webm, *.png, segments.json/zoom.mp4) que rien ne purge
    # entre deux executions -- sans ca, changer de mode laisse les fichiers
    # de l'ancien traîner a cote (glob() de la mauvaise etape, ou simplement
    # des .png/.webm perimes dans l'artefact final).
    mode_marker_name = ".capture_mode"
    video_root = out / "video"
    if video_root.exists() and from_index is None:
        for video_dir in video_root.iterdir():
            marker = video_dir / mode_marker_name
            if marker.exists() and marker.read_text(encoding="utf-8").strip() != args.capture_mode:
                print(f"Mode de capture different de {video_dir.name} -> etape video (et suivantes) regenerees")
                from_index = STEPS.index("video")
                break

    # 1. Scenarios (scenes = fonctionnalite montree + texte dit pendant ce temps)
    scenario_args = ["--duration", str(args.duration)]
    if args.angle:
        scenario_args += ["--angle", args.angle]
    if args.scenario:
        scenario_args += ["--scenario", args.scenario]
    for flag, value in (("--format", args.format), ("--theme", args.theme), ("--hook", args.hook)):
        if value:
            scenario_args += [flag, value]
    run([sys.executable, str(ROOT / "1_generate_script.py"),
         "--n", str(args.n), *scenario_args, "--out", str(scripts_path), *force_flag_for("script")])

    # 2. Voix
    run([sys.executable, str(ROOT / "2_generate_voice.py"),
         "--scripts", str(out / "scripts.json"), "--voice", args.voice,
         "--out", str(out / "audio"), *force_flag_for("voice")])

    scripts = json.loads((out / "scripts.json").read_text(encoding="utf-8"))

    # Un run precedent avec un --n plus grand (ou un --scenario a plus de
    # scenarios) laisse ses reels excedentaires dans output/ indefiniment --
    # ils ne correspondent plus a rien de ce qui est demande maintenant.
    for sub, pattern in ((out / "video", "reel_*"), (out / "audio", "reel_*.*"),
                         (out / "subs", "reel_*.*"), (out / "final", "reel_*.mp4")):
        if not sub.exists():
            continue
        for path in sub.glob(pattern):
            stem = path.stem.split(".")[0]  # reel_04.timeline -> reel_04
            try:
                idx = int(stem.removeprefix("reel_"))
            except ValueError:
                continue
            if idx > len(scripts):
                print(f"Reel {idx} excedentaire (n={len(scripts)}) -> suppression de {path}")
                shutil.rmtree(path) if path.is_dir() else path.unlink()

    for i in range(1, len(scripts) + 1):
        audio_path = out / "audio" / f"reel_{i:02d}.mp3"
        if not audio_path.exists():
            print(f"[{i}] audio manquant, on saute ce reel")
            continue

        # 3. Demo screen-record. En mode screenshots/video_desktop, "features"
        #    (ecrit par 1_generate_script.py dans scripts.json, cf. features.py)
        #    fixe quelles fonctionnalites capturer pour CE reel -- garde le
        #    texte et les captures synchronises sur les memes fonctionnalites.
        video_dir = out / "video" / f"reel_{i:02d}"
        if force_flag_for("video") and video_dir.exists():
            # Purge complete plutot que le nettoyage partiel (par pattern du
            # mode courant) de 3_record_demo.py : sinon les fichiers d'un
            # --capture-mode precedent (png/webm/zoom.mp4/segments.json)
            # restent a cote des nouveaux.
            shutil.rmtree(video_dir)
        feature_ids = scripts[i - 1].get("features") or []
        features_args = ["--features", ",".join(feature_ids)] if feature_ids else []
        # offre_emploi/theme_style : generes par 1_generate_script.py (Gemini)
        # pour ce scenario precis, cf. sa docstring -- rendent la demo
        # coherente avec l'angle plutot que de toujours montrer le meme
        # exemple fige, quel que soit le reel.
        demo_args = []
        if scripts[i - 1].get("offre_emploi"):
            demo_args += ["--job-offer", scripts[i - 1]["offre_emploi"]]
        if scripts[i - 1].get("theme_style"):
            demo_args += ["--theme-style", scripts[i - 1]["theme_style"]]
        run([sys.executable, str(ROOT / "3_record_demo.py"),
             "--url", args.saas_url, "--out", str(video_dir),
             "--mode", args.capture_mode, *features_args, *demo_args, *force_flag_for("video")])
        if video_dir.exists():
            (video_dir / ".capture_mode").write_text(args.capture_mode, encoding="utf-8")

        if args.capture_mode == "screenshots" and not list(video_dir.glob("*.png")):
            print(f"[{i}] pas de captures generees, on saute")
            continue
        if args.capture_mode == "video_desktop" and not (video_dir / "segments.json").exists():
            print(f"[{i}] pas d'enregistrement desktop genere, on saute")
            continue

        # 4. Sous-titres (alignes sur le texte exact du script) + timeline des
        #    scenes : quand la voix commence a parler de chaque fonctionnalite.
        subs_path = out / "subs" / f"reel_{i:02d}.json"
        timeline_path = out / "subs" / f"reel_{i:02d}.timeline.json"
        # Un audio plus recent que ses sous-titres n'a pas ete synthetise pour
        # le meme texte que celui deja transcrit (ex: 1_generate_script.py a
        # regenere scripts.json avec un --n plus grand sans qu'on force cette
        # etape-ci : 2_generate_voice.py a alors resynthetise CE reel tout
        # seul, cf. son propre fingerprint de texte) -- sans cette detection,
        # les sous-titres perimes afficheraient un texte que la voix ne dit
        # plus du tout.
        audio_regenerated = subs_path.exists() and audio_path.stat().st_mtime > subs_path.stat().st_mtime
        subs_force = force_flag_for("subs") or (["--force"] if audio_regenerated else [])
        if audio_regenerated and not force_flag_for("subs"):
            print(f"[{i}] audio plus recent que les sous-titres existants -> regeneration")
        run([sys.executable, str(ROOT / "4_generate_subtitles.py"),
             "--audio", str(audio_path), "--scripts", str(scripts_path), "--index", str(i),
             "--out", str(subs_path), "--timeline-out", str(timeline_path),
             "--model", args.whisper_model, *subs_force])

        # Animations : placees d'apres la timeline (debut de chaque scene).
        #    Un choix d'animations different du dernier montage de ce reel
        #    force 3b et l'assemblage (pas la capture, couteuse).
        anim_video_args, anim_assemble_args = [], []
        if timeline_path.exists():
            anim_video_args, anim_assemble_args = plan_montage(
                scripts[i - 1], json.loads(timeline_path.read_text(encoding="utf-8")), args.anims,
                cards=args.capture_mode == "screenshots", hook=not args.no_hook_overlay)
            if args.capture_mode != "screenshots" and any(s.get("carte") for s in scripts[i - 1].get("scenes", [])):
                print(f"[{i}] cartes texte ignorees hors --capture-mode screenshots (captures montrees a la place)")
        if args.capture_mode != "screenshots":
            # 3c / video mobile : pas de --scene-anim/--highlight/--theme cote montage.
            anim_video_args = []
        anims_marker = video_dir / ".anims"
        anims_signature = json.dumps([anim_video_args, anim_assemble_args])
        previous_signature = anims_marker.read_text(encoding="utf-8") if anims_marker.exists() else json.dumps([[], []])
        anims_force = ["--force"] if previous_signature != anims_signature else []
        if anims_force:
            print(f"[{i}] animations modifiees -> montage et assemblage refaits")

        # 3b/3c. Montage de la video muette, cale sur la timeline : apres les
        #    sous-titres parce qu'il en a besoin. Force des que la capture ou
        #    la timeline ont ete refaites (subs_force couvre les deux cas).
        if args.capture_mode == "screenshots":
            video_path = video_dir / "zoom.mp4"
            run([sys.executable, str(ROOT / "3b_build_video_from_screenshots.py"),
                 "--screens", str(video_dir), "--timeline", str(timeline_path),
                 "--out", str(video_path), *anim_video_args, *(subs_force or anims_force)])
        elif args.capture_mode == "video_desktop":
            video_path = video_dir / "zoom.mp4"
            run([sys.executable, str(ROOT / "3c_build_video_from_recording.py"),
                 "--dir", str(video_dir), "--timeline", str(timeline_path),
                 "--out", str(video_path), *subs_force])
        else:
            videos = list(video_dir.glob("*.webm"))
            if not videos:
                print(f"[{i}] pas de video generee, on saute")
                continue
            video_path = videos[0]

        # 5. Assemblage final -- force des que la video ou les sous-titres
        #    (donc l'audio, cf. subs_force ci-dessus) ont change.
        final_path = out / "final" / f"reel_{i:02d}.mp4"
        run([sys.executable, str(ROOT / "5_assemble.py"),
             "--video", str(video_path), "--audio", str(audio_path),
             "--subs", str(subs_path), "--out", str(final_path), *anim_assemble_args,
             *(force_flag_for("assemble") or subs_force or anims_force)])
        anims_marker.write_text(anims_signature, encoding="utf-8")
        write_caption_file(scripts[i - 1], final_path.with_suffix(".txt"))

    print(f"\nTermine. {args.n} reel(s) dans output/final/")


if __name__ == "__main__":
    main()
