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

from script_text import script_to_text

ROOT = Path(__file__).parent

# Ordre des etapes : forcer une etape force aussi celles d'apres, sinon un
# sous-titre/assemblage "REPRISE" resterait construit sur une video ou un
# audio perimes.
STEPS = ["script", "voice", "video", "subs", "assemble"]


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
    args = parser.parse_args()

    out = Path("output")
    from_index = 0 if args.force else (STEPS.index(args.from_step) if args.from_step else None)

    # Un scenario/angle impose ou une duree differente de l'existant : les
    # sorties en cache ne correspondent plus a la demande -> tout regenerer,
    # sinon la reprise ressortirait silencieusement l'ancien reel.
    scripts_path = out / "scripts.json"
    if from_index is None and scripts_path.exists():
        existing = json.loads(scripts_path.read_text(encoding="utf-8"))
        stale_duration = any(s.get("duree_cible_s") != args.duration for s in existing) and not args.scenario
        if args.scenario or args.angle or stale_duration:
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

        # 3b/3c. Montage de la video muette, cale sur la timeline : apres les
        #    sous-titres parce qu'il en a besoin. Force des que la capture ou
        #    la timeline ont ete refaites (subs_force couvre les deux cas).
        if args.capture_mode == "screenshots":
            video_path = video_dir / "zoom.mp4"
            run([sys.executable, str(ROOT / "3b_build_video_from_screenshots.py"),
                 "--screens", str(video_dir), "--timeline", str(timeline_path),
                 "--out", str(video_path), *subs_force])
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
             "--subs", str(subs_path), "--out", str(final_path),
             *(force_flag_for("assemble") or subs_force)])

    print(f"\nTermine. {args.n} reel(s) dans output/final/")


if __name__ == "__main__":
    main()
