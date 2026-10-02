"""
Declinaisons Instagram d'un reel (run_pipeline.py --plateformes) :

  instagram -> reel_XX.instagram.txt : legende propre a Instagram (1re ligne
               accrocheuse, resume, question, invitation a enregistrer) et
               hashtags limites a config.json instagram.hashtags_max ;
  tiktok ou instagram -> reel_XX.couverture.jpg : couverture 1080x1920 (assets/anim/
               couverture.html), texte dans la zone visible en grille 3:4 et 1:1,
               sur un fond uni aux couleurs du theme (TikTok et Instagram).
  carrousel -> reel_XX_carrousel/01.png... : carrousel 4:5 (1080x1350,
               assets/anim/carrousel.html) -- couverture, une idee par
               diapositive, diapositive finale d'appel a l'action
               (config.json instagram.carrousel_fin) -- + legende.txt.

Les textes viennent du scenario (1_generate_script.py : legende_instagram,
hashtags_instagram, carrousel) ; absents (scenario ancien ou ecrit a la main),
ils sont derives de la legende TikTok et des cartes du reel.

Usage :
    python instagram.py --scripts output/scripts.json --index 1 --final output/final/reel_01.mp4
    python instagram.py ... --plateformes carrousel
"""
import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import catalog
from render_js_anim import render_stills

PLATEFORMES = ("tiktok", "instagram", "carrousel")
CARROUSEL_SIZE = (1080, 1350)
CARROUSEL_MAX = 9  # diapositives ecrites + la finale
BRAND = "OpusCV"


def parse_plateformes(value: str) -> list[str]:
    items = [v.strip().lower() for v in value.split(",") if v.strip()]
    if items == ["all"]:
        return list(PLATEFORMES)
    unknown = [v for v in items if v not in PLATEFORMES]
    if unknown or not items:
        raise argparse.ArgumentTypeError(f"plateforme(s) inconnue(s) {unknown} ; choix : {', '.join(PLATEFORMES)}, all")
    return items


def _stable_pick(options: list, key: str):
    """Choix reproductible (meme reel -> meme variante), sans etat partage."""
    if not options:
        return None
    return options[int(hashlib.sha1(key.encode("utf-8")).hexdigest(), 16) % len(options)]


def instagram_caption(script: dict) -> str:
    cfg = catalog.config().get("instagram") or {}
    legende = (script.get("legende_instagram") or script.get("legende") or "").strip()
    if "enregistr" not in catalog._norm(legende):
        cta = _stable_pick(cfg.get("cta_legende") or [], script.get("titre", "") + legende)
        if cta:
            legende = f"{legende}\n\n{cta}".strip()
    tags = script.get("hashtags_instagram") or script.get("hashtags") or []
    tags = tags[: cfg.get("hashtags_max", 5)]
    return (legende + ("\n\n" + " ".join(tags) if tags else "")).strip() + "\n"


def slide_from_card(card: dict) -> dict | None:
    """Carte du reel -> diapositive {titre, texte} (carrousel derive, faute de carrousel ecrit par l'IA)."""
    kind = card.get("type", "texte")
    if kind == "texte":
        return {"titre": card.get("titre", ""), "texte": card.get("texte", "")}
    if kind == "chiffre":
        return {"titre": f"{card.get('valeur', '')}{card.get('unite', '')}", "texte": card.get("titre", "")}
    if kind == "comparaison":
        return {"titre": card.get("apres", ""), "texte": f"Au lieu de : « {card.get('avant', '')} »"}
    if kind == "liste":
        return {"titre": card.get("titre") or card.get("surtitre", ""), "texte": " · ".join(card.get("points") or [])}
    if kind == "schema":
        return {"titre": card.get("titre", ""), "texte": " → ".join(e.get("label", "") for e in card.get("etapes") or [])}
    if kind == "conversation":
        msgs = card.get("messages") or []
        return {"titre": msgs[0].get("texte", "") if msgs else "", "texte": " ".join(m.get("texte", "") for m in msgs[1:])}
    if kind == "scan":
        return {"titre": card.get("titre", ""), "texte": "À ajouter : " + ", ".join(card.get("manquants") or [])}
    if kind == "impact":
        return {"titre": card.get("texte", ""), "texte": ""}
    if kind == "meme":
        return {"titre": card.get("haut", ""), "texte": card.get("bas", "")}
    return None


def carrousel_slides(script: dict) -> list[dict]:
    """Diapositives {kind, titre, texte} : couverture, points, fin (config.json instagram.carrousel_fin)."""
    written = [s for s in script.get("carrousel") or [] if s.get("titre")]
    if written:
        cover, points = written[0], written[1:]
    else:
        cover = {"titre": script.get("accroche_ecran") or script.get("titre") or "", "texte": ""}
        scenes = script.get("scenes") or []
        points = [slide_from_card(s["carte"]) for s in scenes if s.get("carte")]
        points = [p for p in points if p and p["titre"].strip()]
        if not points:  # reel sans carte : les phrases dites, hors accroche et CTA
            points = [{"titre": s["texte"], "texte": ""} for s in scenes[1:-1] if s.get("texte")]
    fins = (catalog.config().get("instagram") or {}).get("carrousel_fin") or [
        {"titre": "Enregistre ce post", "texte": "Et teste ton CV gratuitement : lien en bio."}]
    fin = _stable_pick(fins, cover.get("titre", ""))
    slides = ([{"kind": "couverture", **cover}] + [{"kind": "point", **p} for p in points][: CARROUSEL_MAX - 2]
              + [{"kind": "fin", "titre": fin.get("titre", ""), "texte": fin.get("texte", "")}])
    return slides


def export(script: dict, final_video: Path, plateformes: list[str]) -> list[Path]:
    """Ecrit les declinaisons demandees a cote de final_video ; -> fichiers ecrits."""
    theme = catalog.get_theme(script.get("theme"))
    base = catalog.anim_params(theme)
    written = []
    caption = instagram_caption(script)
    stem = final_video.with_suffix("")
    with tempfile.TemporaryDirectory() as tmp:
        jobs_story, jobs_carrousel = [], []
        if "instagram" in plateformes:
            txt = final_video.with_suffix(".instagram.txt")
            txt.write_text(caption, encoding="utf-8")
            written.append(txt)
        if "instagram" in plateformes or "tiktok" in plateformes:
            # Couverture commune TikTok / Instagram : fond uni aux couleurs du theme, jamais une capture
            # (une capture floue derriere le titre le rend illisible dans la grille du profil).
            params = {**base, "titre": script.get("accroche_ecran") or script.get("titre") or "", "marque": BRAND}
            if script.get("serie_titre"):  # dessin anime : « Karim cherche un job · ép. 4 »
                params["surtitre"] = f"{script['serie_titre']} · ép. {script['episode']}"
            elif script.get("episode"):
                params["surtitre"] = f"Jour {script['episode']}/30"
            jobs_story.append(("couverture", params, Path(f"{stem}.couverture.jpg")))
        if "carrousel" in plateformes:
            folder = Path(f"{stem}_carrousel")
            if folder.exists():
                for old in folder.glob("*.png"):
                    old.unlink()
            slides = carrousel_slides(script)
            for n, slide in enumerate(slides, 1):
                jobs_carrousel.append(("carrousel", {**base, "kind": slide["kind"], "n": str(n), "total": str(len(slides)),
                                                     "titre": slide["titre"], "texte": slide.get("texte", ""),
                                                     "marque": BRAND}, folder / f"{n:02d}.png"))
            folder.mkdir(parents=True, exist_ok=True)
            (folder / "legende.txt").write_text(caption, encoding="utf-8")
            written.append(folder / "legende.txt")
        if jobs_story:
            written += render_stills(jobs_story)
        if jobs_carrousel:
            written += render_stills(jobs_carrousel, CARROUSEL_SIZE)
    return written


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scripts", type=str, required=True, help="output/scripts.json")
    parser.add_argument("--index", type=int, required=True, help="Numero du reel (1 = premier scenario)")
    parser.add_argument("--final", type=str, required=True, help="Reel final (.mp4) : les fichiers sont ecrits a cote")
    parser.add_argument("--plateformes", type=parse_plateformes, default=["instagram", "carrousel"],
                         help="tiktok (couverture), instagram (legende + couverture), carrousel")
    args = parser.parse_args()
    scripts = json.loads(Path(args.scripts).read_text(encoding="utf-8"))
    if not 1 <= args.index <= len(scripts):
        parser.error(f"--index hors limites (1..{len(scripts)})")
    try:
        files = export(scripts[args.index - 1], Path(args.final), args.plateformes)
    except Exception as e:  # une declinaison ratee ne doit pas faire echouer le reel deja monte
        print(f"ATTENTION: declinaisons Instagram non generees ({e})", file=sys.stderr)
        return
    for f in files:
        print(f"OK -> {f}")


if __name__ == "__main__":
    main()
