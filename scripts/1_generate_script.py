"""
Génère des scripts de reels pour un SaaS de CV, via l'API Gemini.

Usage:
    python 1_generate_script.py --n 5 --out output/scripts.json

Nécessite la variable d'environnement GEMINI_API_KEY.
"""
import argparse
import json
import os
import sys
from pathlib import Path

from google import genai

from features import FEATURES

ANGLES = [
    "avant/apres : CV mal fait vs CV optimise par l'outil (score ATS)",
    "3 erreurs de CV que les recruteurs detestent, + comment l'outil les corrige",
    "demo rapide : upload d'un CV existant -> analyse et optimisation en live",
    "temoignage fictif type : 'mon CV etait invisible pour les ATS, maintenant il passe'",
    "comparatif : reecrire son CV a la main (long, stressant) vs l'optimiser avec l'IA (rapide)",
    "les 33 themes de mise en page, pour un CV qui sort du lot sans sacrifier l'ATS",
]

# Fonctionnalites (features.py, catalogue partage avec 3_record_demo.py) mises
# en avant pour chaque angle -- garantit que le texte du reel parle de ce qui
# est reellement montre a l'ecran en mode screenshots, plutot que les deux
# etant generes independamment et pouvant diverger. "apercu_cv" est ajoute a
# tous les angles : c'est le plan de fin naturel (rendu final du CV).
ANGLE_FEATURES = {
    ANGLES[0]: ["fonctions_ia", "design", "apercu_cv"],
    ANGLES[1]: ["experiences", "apercu_cv"],
    ANGLES[2]: ["identite", "experiences", "apercu_cv"],
    ANGLES[3]: ["experiences", "formation", "apercu_cv"],
    ANGLES[4]: ["identite", "experiences", "competences", "apercu_cv"],
    ANGLES[5]: ["design", "apercu_cv"],
}

PRODUCT_CONTEXT = """Produit : OpusCV (SaaS opuscv.tech), une application qui analyse un CV existant
(PDF ou Word) via l'IA (Gemini), detecte ce qui bloque le passage des filtres ATS des recruteurs,
propose des optimisations concretes, puis regenere un PDF stylise (33 themes disponibles).
L'utilisateur peut aussi decliner son CV par offre d'emploi et le partager via un lien public.
Plan gratuit : 3 CV sauvegardes, 25 actions IA/jour. Plan Pro : illimite.
Ton de marque : direct, concret, oriente resultat (decrocher des entretiens), jamais "corporate"."""

SYSTEM_PROMPT = """Tu es copywriter specialise en contenu court viral (TikTok/Instagram Reels)
pour le SaaS decrit ci-dessous. Base-toi UNIQUEMENT sur ces informations produit reelles,
n'invente pas de fonctionnalites qui n'existent pas :

""" + PRODUCT_CONTEXT + """

Pour l'angle donne, ecris un script de reel de 15 a 20 secondes en francais, avec cette structure STRICTE :
1. HOOK (1 phrase, 2 secondes max, doit arreter le scroll)
2. PROBLEME (1-2 phrases, la douleur concrete du spectateur)
3. DEMO/SOLUTION (2-3 phrases, comment l'outil resout ca, ton naturel pas publicitaire)
4. CTA (1 phrase courte, ex: "essaie gratuitement, lien en bio")

Reponds UNIQUEMENT en JSON valide, sans markdown, sans backticks, format :
{"hook": "...", "probleme": "...", "demo": "...", "cta": "...", "duree_estimee_s": 18}
"""


MODEL_NAME = os.environ.get("GEMINI_MODEL", "gemini-flash-latest")


def generate_script(client: genai.Client, angle: str) -> dict:
    feature_ids = ANGLE_FEATURES.get(angle, [])
    hints = "\n".join(f"- {FEATURES[fid].script_hint}" for fid in feature_ids if fid in FEATURES)
    prompt = f"{SYSTEM_PROMPT}\n\nAngle : {angle}"
    if hints:
        prompt += ("\n\nCe reel va MONTRER A L'ECRAN, dans cet ordre, uniquement ces actions concretes "
                   f"(base ton texte, notamment la partie DEMO/SOLUTION, sur celles-ci) :\n{hints}")
    response = client.models.generate_content(model=MODEL_NAME, contents=prompt)
    text = response.text.strip()
    # Sécurité : au cas où le modèle ajoute des backticks malgré la consigne
    text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        data = {"raw": text, "error": "JSON invalide, voir champ raw"}
    data["angle"] = angle
    # Consomme par 3_record_demo.py (--features) via run_pipeline.py : garde
    # texte et captures d'ecran synchronises sur les memes fonctionnalites.
    data["features"] = feature_ids
    return data


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=5, help="Nombre de scripts a generer")
    parser.add_argument("--out", type=str, default="output/scripts.json")
    parser.add_argument("--force", action="store_true",
                         help="Regenere meme si --out existe deja avec assez de scripts")
    args = parser.parse_args()

    out_path = Path(args.out)
    if not args.force and out_path.exists():
        existing = json.loads(out_path.read_text(encoding="utf-8"))
        if len(existing) >= args.n:
            print(f"REPRISE: {out_path} existe deja avec {len(existing)} script(s), on saute (--force pour regenerer)")
            return

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("ERREUR: variable d'environnement GEMINI_API_KEY manquante", file=sys.stderr)
        sys.exit(1)

    client = genai.Client(api_key=api_key)

    angles = (ANGLES * ((args.n // len(ANGLES)) + 1))[: args.n]
    scripts = []
    for i, angle in enumerate(angles, 1):
        print(f"[{i}/{len(angles)}] Generation script pour angle: {angle}")
        scripts.append(generate_script(client, angle))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(scripts, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OK -> {out_path} ({len(scripts)} scripts)")


if __name__ == "__main__":
    main()
