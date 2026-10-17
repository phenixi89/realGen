"""
Controle des gabarits d'animation (assets/anim/*.html) : chacun est charge dans Chromium avec les couleurs et polices
d'un theme, sa page doit annoncer window.READY, puis on avance l'animation (window.seek) a plusieurs instants. Toute
erreur JavaScript de la page (variable inconnue, courbe invalide...) fait echouer le controle -- ce que py_compile ne voit
pas. Un gabarit qui exige des parametres propres (scene du dessin animé, niveau du jeu, planche civique...) est charge avec
ses valeurs par defaut ; ceux de SANS_PARAMETRES ne sont qu'ouverts (pas de seek).

Chaque profil de mouvement de catalog/config.json (« mouvements ») est essaye : un gabarit doit tourner avec les courbes
de toutes les chaines.

Usage :
    python scripts/verif_gabarits.py               # tous les gabarits, tous les profils
    python scripts/verif_gabarits.py carte cta     # certains gabarits
    python scripts/verif_gabarits.py --theme neon_nuit --instants 0,0.5,1
"""
import argparse
import sys
from pathlib import Path
from urllib.parse import urlencode

import catalog
from render_js_anim import ANIM_DIR, READY_TIMEOUT_MS, SIZE

SANS_PARAMETRES: set[str] = set()   # gabarits qui ne se chargent pas sans parametres propres (aucun connu)


def _instants(duration: float, extra: list[float]) -> list[float]:
    return sorted({0.0, *(round(duration * f, 3) for f in (0.15, 0.4, 0.7, 1.0)), *extra})


def verifier(noms: list[str], theme: dict, profils: dict[str, dict], extra: list[float]) -> list[str]:
    from playwright.sync_api import sync_playwright

    errors = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            for nom in noms:
                for profil, courbes in profils.items():
                    page = browser.new_page(viewport={"width": SIZE[0], "height": SIZE[1]})
                    problemes: list[str] = []
                    page.on("pageerror", lambda e, pb=problemes: pb.append(f"erreur JS : {e}"))
                    page.on("console", lambda m, pb=problemes: m.type == "error" and pb.append(f"console : {m.text}"))
                    try:
                        params = {**catalog.anim_params(theme), **courbes, "render": "1"}
                        page.goto((ANIM_DIR / f"{nom}.html").as_uri() + "?" + urlencode(params))
                        page.wait_for_function("window.READY === true", timeout=READY_TIMEOUT_MS)
                        if nom not in SANS_PARAMETRES:
                            duration = float(page.evaluate("window.DURATION") or 0)
                            for t in _instants(duration, extra):
                                page.evaluate(f"window.seek({t}); 0")
                    except Exception as e:  # noqa: BLE001 -- on rapporte, on ne s'arrete pas au premier echec
                        problemes.append(f"{type(e).__name__} : {str(e).splitlines()[0][:160]}")
                    finally:
                        page.close()
                    for pb in dict.fromkeys(problemes):
                        errors.append(f"{nom} [{profil}] : {pb}")
                    print(f"{'OK ' if not problemes else 'KO '} {nom} [{profil}]")
        finally:
            browser.close()
    return errors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("gabarits", nargs="*", help="Gabarits a controler (defaut : tous)")
    parser.add_argument("--theme", default=None, help="Theme (catalog/themes.json) ; defaut : le premier")
    parser.add_argument("--instants", default="", help="Instants supplementaires du seek, en s, separes par des virgules")
    args = parser.parse_args()

    noms = args.gabarits or sorted(p.stem for p in ANIM_DIR.glob("*.html"))
    inconnus = [n for n in noms if not (ANIM_DIR / f"{n}.html").exists()]
    if inconnus:
        sys.exit(f"Gabarit(s) inconnu(s) : {', '.join(inconnus)}")
    profils = {pid: catalog.courbes_mouvement(pid) for pid in catalog.mouvements()}
    extra = [float(x) for x in args.instants.split(",") if x.strip()]
    errors = verifier(noms, catalog.get_theme(args.theme), profils, extra)
    if errors:
        print(f"\n{len(errors)} probleme(s) :\n  " + "\n  ".join(errors))
        sys.exit(1)
    print(f"\nOK : {len(noms)} gabarit(s) x {len(profils)} profil(s) de mouvement")


if __name__ == "__main__":
    main()
