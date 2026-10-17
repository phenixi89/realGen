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
    python render_js_anim.py --spec scene --scene ma_scene.json --duration 20 --out /tmp/scene.mp4
"""
import argparse
import base64
import io
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import parse_qsl, urlencode

from timeline import FPS  # cadence unique du montage (30 i/s)

ANIM_DIR = Path(__file__).resolve().parent.parent / "assets" / "anim"
SIZE = (1080, 1920)
READY_TIMEOUT_MS = 15000
# Flou de mouvement : chaque image est la moyenne de trois instants (1/4, 1/2, 1/4) pris a une
# demi-image d'ecart autour de son instant -- l'effet d'une camera dont l'obturateur reste ouvert le
# temps d'une image. Sans lui, un element qui bouge vite apparait net a chaque image, donc haché.
# Les demi-images sont partagees entre deux images voisines (2 prises de vue par image au lieu de 3)
# et une animation a l'arret n'est rendue qu'une fois. REALGEN_FLOU=0 (run_pipeline.py --sans-flou,
# render_js_anim.py --sans-flou) : sans flou, rendu 2 fois plus rapide.
FLOU = os.environ.get("REALGEN_FLOU", "1") != "0"
# Jamais de flou sur ces gabarits : le jeu rétro est du pixel art (le flou le salirait) et les traits du dessin animé
# « bouillonnent » volontairement, image par image, comme à la main. Ce sont aussi les rendus les plus longs.
SANS_FLOU = {"jeu", "scene"}


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


def _fusionner(avant: bytes, centre: bytes, apres: bytes, transparent: bool):
    """
    Moyenne 1/4, 1/2, 1/4 des trois prises de vue. Alpha pre-multiplie (mode PIL "RGBa") : sans lui,
    les bords des elements sur fond transparent prennent un liseré sombre.
    """
    from PIL import Image

    mode = "RGBa" if transparent else "RGB"
    a, b, c = (Image.open(io.BytesIO(x)).convert(mode) for x in (avant, centre, apres))
    out = Image.blend(Image.blend(a, c, 0.5), b, 0.5)
    return out.convert("RGBA") if transparent else out


def render_frames(name: str, params: dict, out_dir: Path, duration: float | None = None,
                  fps: int = FPS, transparent: bool = True, sons: list | None = None,
                  flou: bool | None = None) -> int:
    """
    -> nombre d'images ecrites dans out_dir (00000.png, 00001.png...).
    duration=None : duree naturelle du gabarit (window.DURATION) ; au-dela,
    seek() fige/prolonge l'animation, ce qui permet de caler un gabarit sur
    une scene plus longue que lui.
    sons : liste completee par les bruitages publies par la page (window.SONS,
    dessin anime : [{"t", "name", "duration"?, "gain"?}], t depuis le debut du clip).
    flou : flou de mouvement (defaut FLOU, sauf gabarits de SANS_FLOU) ; False = une prise de vue nette par image.
    """
    from playwright.sync_api import sync_playwright

    flou = (FLOU if flou is None else flou) and name not in SANS_FLOU
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
            if sons is not None:
                sons.extend(c for c in page.evaluate("window.SONS || []") if c["t"] < total)
            count = max(1, round(total * fps))

            # Capture par le protocole DevTools avec optimizeForSpeed (PNG peu compresse) : ~4 fois plus rapide que
            # page.screenshot() pour des images strictement identiques ; repli sur page.screenshot() si indisponible.
            cdp = None
            try:
                cdp = page.context.new_cdp_session(page)
                if transparent:   # ce que fait page.screenshot(omit_background=True)
                    cdp.send("Emulation.setDefaultBackgroundColorOverride", {"color": {"r": 0, "g": 0, "b": 0, "a": 0}})
            except Exception:  # noqa: BLE001
                cdp = None

            def shot(t: float) -> bytes:
                nonlocal cdp
                # "; 0" : ne renvoie rien a Python (sinon serialisation de l'objet GSAP)
                page.evaluate(f"window.seek({max(t, 0):.5f}); 0")
                if cdp is not None:
                    try:
                        # Attend que le navigateur ait affiche l'etat qu'on vient de poser : sans cela, la capture directe
                        # prend parfois l'image precedente (page.screenshot() fait cette attente lui-meme).
                        page.evaluate("new Promise((ok) => requestAnimationFrame(() => requestAnimationFrame(() => ok(0))))")
                        return base64.b64decode(cdp.send("Page.captureScreenshot", {
                            "format": "png", "optimizeForSpeed": True, "fromSurface": True})["data"])
                    except Exception:  # noqa: BLE001
                        cdp = None
                return page.screenshot(omit_background=transparent)

            if not flou:
                for i in range(count):
                    (out_dir / f"{i:05d}.png").write_bytes(shot(i / fps))
                return count

            nettes: dict[int, bytes] = {}   # instants i / fps, calcules une fois (cle = image)
            demies: dict[int, bytes] = {}   # instants (k - 0.5) / fps, partages par les images k - 1 et k

            def nette(i: int) -> bytes:
                if i not in nettes:
                    nettes[i] = shot(i / fps)
                return nettes[i]

            def demie(k: int) -> bytes:
                if k not in demies:
                    demies[k] = shot((k - 0.5) / fps)
                return demies[k]

            for k in range(count):
                centre = nette(k)
                # Identique a la voisine : l'animation est a l'arret de ce cote, la demi-image aussi.
                avant_fixe = k == 0 or nette(k - 1) == centre
                apres_fixe = nette(k + 1) == centre
                dest = out_dir / f"{k:05d}.png"
                if avant_fixe and apres_fixe:
                    dest.write_bytes(centre)
                else:
                    _fusionner(centre if avant_fixe else demie(k), centre, centre if apres_fixe else demie(k + 1),
                               transparent).save(dest, compress_level=1)   # fichiers temporaires : compression minimale (4x plus vite)
                nettes.pop(k - 1, None)
                demies.pop(k, None)
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


def render_clip(name: str, params: dict, out_path: Path, duration: float, fps: int = FPS) -> list[dict]:
    """Clip MP4 opaque (mode scene), meme encodage que les clips de 3b. -> bruitages du clip (window.SONS)."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sons: list[dict] = []
    with tempfile.TemporaryDirectory() as tmp:
        render_frames(name, params, Path(tmp), duration=duration, fps=fps, transparent=False, sons=sons)
        subprocess.run([
            "ffmpeg", "-y", "-loglevel", "error", "-framerate", str(fps), "-i", str(Path(tmp) / "%05d.png"),
            "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", str(out_path),
        ], check=True)
    return sons


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", type=str, required=True, help='Gabarit + parametres, ex: "score_ats?from=35&to=92"')
    parser.add_argument("--out", type=str, required=True, help="Dossier (images PNG) ou fichier .mp4 (clip opaque)")
    parser.add_argument("--duration", type=float, default=None, help="Duree en s (defaut : celle du gabarit)")
    parser.add_argument("--size", type=str, default=None,
                         help="Image fixe LxH (ex : 1080x1350) : --out en .png/.jpg, etat final du gabarit")
    parser.add_argument("--scene", type=str, default=None,
                         help="Fichier JSON d'une scene de dessin anime (gabarit scene) : passe en parametre ?scene=")
    parser.add_argument("--sans-flou", action="store_true",
                         help="Sans flou de mouvement (une prise de vue nette par image : rendu 2 fois plus rapide)")
    args = parser.parse_args()
    if args.sans_flou:
        os.environ["REALGEN_FLOU"] = "0"
        globals()["FLOU"] = False

    name, params = parse_spec(args.spec)
    if args.scene:
        params["scene"] = json.dumps(json.loads(Path(args.scene).read_text(encoding="utf-8")), ensure_ascii=False)
    out = Path(args.out)
    if out.suffix.lower() in (".png", ".jpg", ".jpeg"):
        w, _, h = (args.size or f"{SIZE[0]}x{SIZE[1]}").partition("x")
        render_stills([(name, params, out)], (int(w), int(h)))
    elif out.suffix == ".mp4":
        if args.duration is None:
            parser.error("--duration est obligatoire pour un clip .mp4")
        sons = render_clip(name, params, out, args.duration)
        if sons:  # bruitages (dessin anime) : a cote du clip, pour l'ecoute / le mixage
            out.with_suffix(".sons.json").write_text(json.dumps(sons, ensure_ascii=False), encoding="utf-8")
    else:
        if out.exists():
            shutil.rmtree(out)
        n = render_frames(name, params, out, args.duration)
        print(f"{n} images")
    print(f"OK -> {out}")


if __name__ == "__main__":
    main()
