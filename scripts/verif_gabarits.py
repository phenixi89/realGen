"""
Controle des gabarits d'animation (assets/anim/*.html) : chacun est charge dans Chromium avec les couleurs et polices
d'un theme, sa page doit annoncer window.READY, puis on avance l'animation (window.seek) a plusieurs instants. Toute
erreur JavaScript de la page (variable inconnue, courbe invalide...) fait echouer le controle -- ce que py_compile ne voit
pas. Un gabarit qui exige des parametres propres (scene du dessin animé, niveau du jeu, planche civique...) est charge avec
ses valeurs par defaut (gabarits a planches : chaque planche de PLANCHES) ; ceux de SANS_PARAMETRES ne sont qu'ouverts (pas de seek).

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
# Gabarits a planches (parametre mode) : chaque planche est chargee, avec des parametres d'exemple (le mode par defaut
# seul laissait passer une erreur dans une autre planche).
PLANCHES: dict[str, list[dict]] = {
    "civique": [
        {"mode": "quiz", "texte": "Qui nomme le Premier ministre ?", "points": "Le Sénat|Le président|Le maire", "bonne": "2"},
        {"mode": "quiz", "texte": "Qui nomme le Premier ministre ?", "points": "Le Sénat|Le président|Le maire|Le juge", "bonne": "2"},
        {"mode": "duel", "texte": "Qui vote la loi ?", "gauche": "Le Parlement", "droite": "Le préfet", "bonne": "1"},
        {"mode": "intrus", "texte": "Trouve l'intrus", "points": "Liberté|Égalité|Fraternité|Vitesse", "bonne": "4"},
        {"mode": "relier", "texte": "Relie", "gauche": "1789|1958", "droite": "Révolution|Ve République"},
        {"mode": "definition", "mot": "Laïcité", "sens": "L'État est neutre."},
        {"mode": "frise", "texte": "Les dates", "jalons": "1789~Révolution|1958~Ve République"},
        {"mode": "indices", "texte": "Qui suis-je ?", "points": "Indice 1|Indice 2|Indice 3", "reponse": "Marianne"},
        {"mode": "citation", "texte": "La liberté consiste à faire tout ce qui ne nuit pas à *autrui*", "source": "Article 4, Déclaration de 1789"},
        {"mode": "chapitre", "quand": "14 juillet 1789", "texte": "Des Parisiens entrent dans la *Bastille*.", "icone": "drapeau", "chapitre": "1"},
        {"mode": "chapitre", "quand": "", "texte": "Le peuple se réunit à Paris.", "chapitre": "2"},
        {"mode": "situation", "texte": "Ton voisin tombe dans l'escalier et ne répond plus.", "icone": "sante"},
        {"mode": "liste", "texte": "À retenir", "points": "Un|Deux|Trois"},
        {"mode": "etapes", "texte": "Le parcours", "points": "Un|Deux|Trois"},
        {"mode": "avant_apres", "avant": "Le coq est officiel", "apres": "Le coq n'est pas officiel"},
        {"mode": "chiffre", "grand": "18 ans", "legende": "pour voter"},
        {"mode": "retenir", "texte": "La loi est la même pour *tous*"},
        {"mode": "accroche", "icone": "urne"},
        {"mode": "fin", "title": "Une question par jour", "sub": "Abonne-toi", "button": "S'abonner"},
    ],
}


def _instants(duration: float, extra: list[float]) -> list[float]:
    return sorted({0.0, *(round(duration * f, 3) for f in (0.15, 0.4, 0.7, 1.0)), *extra})


def verifier(noms: list[str], theme: dict, profils: dict[str, dict], extra: list[float]) -> list[str]:
    from playwright.sync_api import sync_playwright

    errors = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            for nom, planche in [(n, pl) for n in noms for pl in (PLANCHES.get(n) or [{}])]:
                for profil, courbes in profils.items():
                    page = browser.new_page(viewport={"width": SIZE[0], "height": SIZE[1]})
                    problemes: list[str] = []
                    page.on("pageerror", lambda e, pb=problemes: pb.append(f"erreur JS : {e}"))
                    page.on("console", lambda m, pb=problemes: m.type == "error" and pb.append(f"console : {m.text}"))
                    try:
                        params = {**catalog.anim_params(theme), **courbes, **planche, "render": "1"}
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
                    nom_planche = f"{nom}?mode={planche['mode']}" if planche.get("mode") else nom
                    for pb in dict.fromkeys(problemes):
                        errors.append(f"{nom_planche} [{profil}] : {pb}")
                    print(f"{'OK ' if not problemes else 'KO '} {nom_planche} [{profil}]")
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
