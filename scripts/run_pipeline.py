"""
Orchestrateur : enchaine script -> voix -> demo -> sous-titres -> assemblage
pour generer N reels en une seule commande.

Usage:
    python run_pipeline.py --n 3 --saas-url https://tonapp.com --voice Kore
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

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
    parser.add_argument("--capture-mode", type=str, default="video", choices=["video", "screenshots"],
                         help="video = enregistrement mobile continu ; "
                              "screenshots = captures desktop animees en zoom in/out au montage")
    parser.add_argument("--force", action="store_true",
                         help="Ignore les sorties existantes et regenere tout depuis zero (equivalent a --from-step script)")
    parser.add_argument("--from-step", type=str, choices=STEPS, default=None,
                         help="Force la regeneration a partir de cette etape (et toutes celles d'apres) ; "
                              "les etapes precedentes restent en reprise si deja presentes")
    args = parser.parse_args()

    out = Path("output")
    from_index = 0 if args.force else (STEPS.index(args.from_step) if args.from_step else None)

    def force_flag_for(step: str) -> list[str]:
        return ["--force"] if from_index is not None and STEPS.index(step) >= from_index else []

    # 1. Scripts
    run([sys.executable, str(ROOT / "1_generate_script.py"),
         "--n", str(args.n), "--out", str(out / "scripts.json"), *force_flag_for("script")])

    # 2. Voix
    run([sys.executable, str(ROOT / "2_generate_voice.py"),
         "--scripts", str(out / "scripts.json"), "--voice", args.voice,
         "--out", str(out / "audio"), *force_flag_for("voice")])

    scripts = json.loads((out / "scripts.json").read_text(encoding="utf-8"))

    for i in range(1, len(scripts) + 1):
        audio_path = out / "audio" / f"reel_{i:02d}.mp3"
        if not audio_path.exists():
            print(f"[{i}] audio manquant, on saute ce reel")
            continue

        # 3. Demo screen-record (meme demo reutilisee pour chaque reel ici ;
        #    adapte play_demo_steps() / capture_pc_screenshots() dans
        #    3_record_demo.py pour varier les parcours)
        video_dir = out / "video" / f"reel_{i:02d}"
        run([sys.executable, str(ROOT / "3_record_demo.py"),
             "--url", args.saas_url, "--out", str(video_dir),
             "--mode", args.capture_mode, *force_flag_for("video")])

        if args.capture_mode == "screenshots":
            if not list(video_dir.glob("*.png")):
                print(f"[{i}] pas de captures generees, on saute")
                continue
            # 3b. Anime les captures fixes (zoom in/out) en une video muette,
            #     consommee ensuite par 5_assemble.py comme n'importe quelle
            #     autre video source.
            video_path = video_dir / "zoom.mp4"
            run([sys.executable, str(ROOT / "3b_build_video_from_screenshots.py"),
                 "--screens", str(video_dir), "--out", str(video_path), *force_flag_for("video")])
        else:
            videos = list(video_dir.glob("*.webm"))
            if not videos:
                print(f"[{i}] pas de video generee, on saute")
                continue
            video_path = videos[0]

        # 4. Sous-titres
        subs_path = out / "subs" / f"reel_{i:02d}.srt"
        run([sys.executable, str(ROOT / "4_generate_subtitles.py"),
             "--audio", str(audio_path), "--out", str(subs_path),
             "--model", args.whisper_model, *force_flag_for("subs")])

        # 5. Assemblage final
        final_path = out / "final" / f"reel_{i:02d}.mp4"
        run([sys.executable, str(ROOT / "5_assemble.py"),
             "--video", str(video_path), "--audio", str(audio_path),
             "--subs", str(subs_path), "--out", str(final_path), *force_flag_for("assemble")])

    print(f"\nTermine. {args.n} reel(s) dans output/final/")


if __name__ == "__main__":
    main()
