"""
Rend un gabarit d'animation HTML/JS (assets/anim/*.html) en images, via
Playwright -- deja utilise par 3_record_demo.py, donc aucune dependance en
plus. Rendu image par image : la page expose window.seek(t) et on capture
l'etat exact a chaque 1/FPS s, plutot qu'enregistrer en temps reel (images
sautees, pas de transparence).

Usages dans le pipeline (run_pipeline.py --anims, et instagram.py pour les images fixes) :
  - overlay   : PNG transparents poses par-dessus la video (5_assemble.py) ;
  - scene     : clip MP4 plein cadre qui remplace les captures d'une scene
                (3b_build_video_from_screenshots.py) ;
  - highlight : PNG transparents incrustes sur un clip de capture (3b) ;
  - stills    : images fixes (etat final du gabarit), a une taille libre --
                couverture et carrousel Instagram (render_stills).

Specification d'une animation : "gabarit?param=valeur&..." (ex:
"score_ats?from=35&to=92"), parse par parse_spec().

Usage (test/apercu d'un gabarit) :
    python render_js_anim.py --spec "score_ats?from=35&to=92" --out /tmp/frames
    python render_js_anim.py --spec cta --duration 4 --out /tmp/cta.mp4
    python render_js_anim.py --spec "carrousel?kind=couverture&titre=3 erreurs" --size 1080x1350 --out /tmp/s.png
"""
import argparse
import shutil
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import parse_qsl, urlencode

ANIM_DIR = Path(__file__).resolve().parent.parent / "assets" / "anim"
FPS = 25
SIZE = (1080, 1920)
READY_TIMEOUT_MS = 15000


def parse_spec(spec: str) -> tuple[str, dict[str, str]]:
    name, _, query = spec.partition("?")
    return name.strip(), dict(parse_qsl(query, keep_blank_values=True))


def template_path(name: str) -> Path:
    path = ANIM_DIR / f"{name}.html"
    if not path.exists():
        available = ", ".join(sorted(p.stem for p in ANIM_DIR.glob("*.html")))
        raise FileNotFoundError(f"Gabarit d'animation inconnu '{name}' (disponibles : {available})")
    return path


def file_uri(path: str | Path) -> str:
    return Path(path).resolve().as_uri()


def render_frames(name: str, params: dict, out_dir: Path, duration: float | None = None,
                  fps: int = FPS, transparent: bool = True) -> int:
    """
    -> nombre d'images ecrites dans out_dir (00000.png, 00001.png...).
    duration=None : duree naturelle du gabarit (window.DURATION) ; au-dela,
    seek() fige/prolonge l'animation, ce qui permet de caler un gabarit sur
    une scene plus longue que lui.
    """
    from playwright.sync_api import sync_playwright

    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("*.png"):
        old.unlink()
    url = template_path(name).as_uri() + "?" + urlencode({**params, "render": "1"})
    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page = browser.new_page(viewport={"width": SIZE[0], "height": SIZE[1]})
            page.goto(url)
            page.wait_for_function("window.READY === true", timeout=READY_TIMEOUT_MS)
            total = duration if duration is not None else page.evaluate("window.DURATION")
            count = max(1, round(total * fps))
            for i in range(count):
                # "; 0" : ne renvoie rien a Python (sinon serialisation de l'objet GSAP)
                page.evaluate(f"window.seek({i / fps}); 0")
                page.screenshot(path=str(out_dir / f"{i:05d}.png"), omit_background=transparent)
        finally:
            browser.close()
    return count


def render_stills(jobs: list[tuple[str, dict, Path]], size: tuple[int, int] = SIZE) -> list[Path]:
    """
    Images fixes : chaque (gabarit, parametres, fichier .png/.jpg) est rendu a
    l'etat final de son animation (window.DURATION), en une seule session de
    navigateur. Taille libre (ex : 1080x1350 pour un carrousel Instagram).
    """
    from playwright.sync_api import sync_playwright

    written = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page = browser.new_page(viewport={"width": size[0], "height": size[1]})
            for name, params, out in jobs:
                out = Path(out)
                out.parent.mkdir(parents=True, exist_ok=True)
                page.goto(template_path(name).as_uri() + "?" + urlencode({**params, "render": "1"}))
                page.wait_for_function("window.READY === true", timeout=READY_TIMEOUT_MS)
                page.evaluate("window.seek(window.DURATION); 0")
                jpeg = out.suffix.lower() in (".jpg", ".jpeg")
                page.screenshot(path=str(out), type="jpeg" if jpeg else "png", **({"quality": 92} if jpeg else {}))
                written.append(out)
        finally:
            browser.close()
    return written


def render_clip(name: str, params: dict, out_path: Path, duration: float, fps: int = FPS):
    """Clip MP4 opaque (mode scene), meme encodage que les clips de 3b."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        render_frames(name, params, Path(tmp), duration=duration, fps=fps, transparent=False)
        subprocess.run([
            "ffmpeg", "-y", "-loglevel", "error", "-framerate", str(fps), "-i", str(Path(tmp) / "%05d.png"),
            "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", str(out_path),
        ], check=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", type=str, required=True, help='Gabarit + parametres, ex: "score_ats?from=35&to=92"')
    parser.add_argument("--out", type=str, required=True, help="Dossier (images PNG) ou fichier .mp4 (clip opaque)")
    parser.add_argument("--duration", type=float, default=None, help="Duree en s (defaut : celle du gabarit)")
    parser.add_argument("--size", type=str, default=None,
                         help="Image fixe LxH (ex : 1080x1350) : --out en .png/.jpg, etat final du gabarit")
    args = parser.parse_args()

    name, params = parse_spec(args.spec)
    out = Path(args.out)
    if out.suffix.lower() in (".png", ".jpg", ".jpeg"):
        w, _, h = (args.size or f"{SIZE[0]}x{SIZE[1]}").partition("x")
        render_stills([(name, params, out)], (int(w), int(h)))
    elif out.suffix == ".mp4":
        if args.duration is None:
            parser.error("--duration est obligatoire pour un clip .mp4")
        render_clip(name, params, out, args.duration)
    else:
        if out.exists():
            shutil.rmtree(out)
        n = render_frames(name, params, out, args.duration)
        print(f"{n} images")
    print(f"OK -> {out}")


if __name__ == "__main__":
    main()
