"""
Apercus de la console (docs/apercus/) : ce que le menu de lancement montre a cote de
chaque choix, pour choisir en voyant plutot qu'en lisant des identifiants.

  themes/<id>.jpg       couverture du reel aux couleurs et polices du theme
  cartes/<type>.jpg     chaque carte animee (gabarit de assets/anim/, texte d'exemple)
  decors/<id>.jpg       chaque decor du dessin anime, avec Lea et Karim (bas de l'image, 3:4)
  personnages/<id>.jpg  chaque personnage du dessin anime (3:4)
  niveaux/<id>.jpg      chaque niveau du jeu video (Martin et Lea, une replique d'exemple)
  boss/<id>.jpg         chaque boss du jeu video, dans la plaine
  voix/<id>.mp3         une phrase dite par chaque voix (enregistrements de CTA, assets/voix_cta/)
  ambiances/<id>.mp3    8 s de chaque musique (synthese de audio_gen.py, ou morceau depose)

A relancer apres un ajout au catalogue (theme, decor, personnage, voix, ambiance) :
    python scripts/apercus.py            # tout
    python scripts/apercus.py --seulement themes,decors
Les fichiers deja presents sont gardes (--force pour tout refaire).
"""
import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import catalog  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "apercus"
TAILLE = (270, 480)   # vignette 9:16 (le rendu se fait en 1080x1920 puis reduit)
TITRE_THEME = "Ton CV passe-t-il les filtres ?"
SORTES = ("themes", "cartes", "decors", "personnages", "niveaux", "boss", "voix", "ambiances")


def _reduire(png: Path, jpg: Path):
    """Vignette ; dessin anime : seulement le bas de l'image (3:4), le haut du cadre est vide sans bulle."""
    jpg.parent.mkdir(parents=True, exist_ok=True)
    dessin = jpg.parent.name in ("decors", "personnages")
    vf = "crop=1080:1440:0:480,scale=270:360" if dessin else f"scale={TAILLE[0]}:{TAILLE[1]}"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(png), "-vf", vf, "-q:v", "5", str(jpg)], check=True)


def _images(jobs: list[tuple[str, dict, Path]], force: bool):
    """Rendu des gabarits (etat final de l'animation) puis vignettes JPEG."""
    from render_js_anim import render_stills
    jobs = [j for j in jobs if force or not j[2].exists()]
    if not jobs:
        return
    with tempfile.TemporaryDirectory() as tmp:
        bruts = [(name, params, Path(tmp) / f"{i}.png") for i, (name, params, _) in enumerate(jobs)]
        render_stills(bruts)
        for (_, _, png), (_, _, jpg) in zip(bruts, jobs):
            _reduire(png, jpg)
            print(f"  {jpg.relative_to(ROOT)}")


def _scene(fond: str, objets: list[dict]) -> dict:
    return {"scene": json.dumps({"fond": fond, "objets": objets, "actions": [], "dessine": False,
                                 "echelle": 0.95, "sol": 1720}, ensure_ascii=False)}


def themes_jobs() -> list:
    return [("couverture", {**catalog.anim_params(t), "titre": TITRE_THEME, "surtitre": t["nom"]},
             OUT / "themes" / f"{t['id']}.jpg") for t in catalog.themes()]


# Texte d'exemple de chaque carte (jamais de chiffre presente comme reel).
EXEMPLES_CARTES = {
    "texte": {"surtitre": "Erreur n° 1", "titre": "Un CV sans titre de poste", "texte": "Le recruteur ne sait pas ce que tu vises."},
    "chiffre": {"surtitre": "Le temps de lecture", "valeur": "6", "unite": "s", "titre": "pour juger ton CV"},
    "comparaison": {"surtitre": "Ta phrase", "avant": "Gestion des réseaux sociaux", "apres": "J'ai relancé le compte Instagram de la boutique"},
    "liste": {"surtitre": "Avant d'envoyer", "titre": "Ta checklist", "points": "Un titre précis|Tes vrais résultats|Un PDF propre"},
    "schema": {}, "conversation": {}, "scan": {},
    "impact": {"texte": "Personne ne lit ton CV en entier", "mot": "personne"},
    "meme": {},
}


def cartes_jobs() -> list:
    base = catalog.anim_params(None)
    return [(gabarit, {**base, **EXEMPLES_CARTES.get(kind, {})}, OUT / "cartes" / f"{kind}.jpg")
            for kind, gabarit in catalog.CARD_TYPES.items()]


def decors_jobs() -> list:
    duo = [{"id": "lea", "type": "lea", "x": 250, "regard": "droite"}, {"id": "karim", "type": "karim", "x": 820, "regard": "gauche"}]
    return [("scene", _scene(f["id"], duo), OUT / "decors" / f"{f['id']}.jpg") for f in catalog.dessins()["fonds"]]


def personnages_jobs() -> list:
    return [("scene", _scene("vide", [{"id": p, "type": p, "x": 540, "regard": "droite"}]), OUT / "personnages" / f"{p}.jpg")
            for p in catalog.personnages()]


def _jeu(niveau: str, boss: str, replique: str) -> dict:
    """Scene du jeu video a l'etat final (assets/anim/jeu.html) : une replique de Lea affichee en entier."""
    plan = {"niveau": niveau, "boss": boss, "quete": "DÉCROCHER L'ENTRETIEN", "duree": 6,
            "etat": {"coeurs": 3, "xp": 40, "niv": 2, "bossPv": 100},
            "repliques": [{"qui": "lea", "texte": replique, "t": 0.1, "duree": 1.0}], "evenements": []}
    return {"plan": json.dumps(plan, ensure_ascii=False), "dur": "6"}


def niveaux_jobs() -> list:
    return [("jeu", _jeu(n["id"], "", "Bienvenue dans la quête, Martin !"), OUT / "niveaux" / f"{n['id']}.jpg") for n in catalog.jeu()["niveaux"]]


def boss_jobs() -> list:
    return [("jeu", _jeu("plaine", b["id"], f"Attention : {b['nom']} !"), OUT / "boss" / f"{b['id']}.jpg") for b in catalog.jeu()["boss"]]


def voix(force: bool):
    """Un enregistrement de CTA par voix (le premier par ordre de nom), en MP3 (lisible partout, Safari compris)."""
    for v in dict.fromkeys([x["id"] for x in catalog.voices()] + [p["voix"] for p in catalog.personnages().values()]):
        sources = sorted((ROOT / "assets" / "voix_cta").glob(f"{v}_*.ogg"))
        out = OUT / "voix" / f"{v}.mp3"
        if not sources or (out.exists() and not force):
            continue
        out.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(sources[0]), "-ac", "1", "-b:a", "64k", str(out)], check=True)
        print(f"  {out.relative_to(ROOT)}")


def ambiances(force: bool):
    import numpy as np
    import audio_gen
    for a in catalog.ambiances():
        out = OUT / "ambiances" / f"{a['id']}.mp3"
        if out.exists() and not force:
            continue
        x = audio_gen.load_music(8.0, a["id"])[: int(8 * audio_gen.SR)]
        fade = int(0.8 * audio_gen.SR)
        x[-fade:] *= np.linspace(1, 0, fade)
        out.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory() as tmp:
            wav = Path(tmp) / "a.wav"
            audio_gen.write_wav(wav, 0.5 * x / (np.max(np.abs(x)) or 1))
            subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(wav), "-ac", "1", "-b:a", "64k", str(out)], check=True)
        print(f"  {out.relative_to(ROOT)}")


def main():
    ap = argparse.ArgumentParser(description="Apercus de la console (docs/apercus/)")
    ap.add_argument("--seulement", default="", help=f"sortes a produire, separees par des virgules ({', '.join(SORTES)})")
    ap.add_argument("--force", action="store_true", help="refait aussi les apercus deja presents")
    args = ap.parse_args()
    voulues = [s for s in args.seulement.split(",") if s] or list(SORTES)
    jobs = []
    for s in voulues:
        if s not in SORTES:
            ap.error(f"sorte inconnue : {s}")
        if s in ("themes", "cartes", "decors", "personnages", "niveaux", "boss"):
            jobs += globals()[f"{s}_jobs"]()
    _images(jobs, args.force)
    if "voix" in voulues:
        voix(args.force)
    if "ambiances" in voulues:
        ambiances(args.force)
    print(f"OK -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
