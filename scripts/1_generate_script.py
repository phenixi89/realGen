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

import google.generativeai as genai

ANGLES = [
    "avant/apres : CV mal fait vs CV genere par l'outil",
    "3 erreurs de CV que les recruteurs detestent, + solution via l'outil",
    "demo rapide : upload d'infos -> CV genere en live",
    "temoignage fictif type : 'j'ai decroche un entretien grace a ce CV'",
    "comparatif : CV fait a la main (long, stressant) vs avec l'IA (rapide)",
]

SYSTEM_PROMPT = """Tu es copywriter specialise en contenu court viral (TikTok/Instagram Reels)
pour un SaaS qui genere des CV automatiquement avec l'IA.

Pour l'angle donne, ecris un script de reel de 15 a 20 secondes en francais, avec cette structure STRICTE :
1. HOOK (1 phrase, 2 secondes max, doit arreter le scroll)
2. PROBLEME (1-2 phrases, la douleur concrete du spectateur)
3. DEMO/SOLUTION (2-3 phrases, comment l'outil resout ca, ton naturel pas publicitaire)
4. CTA (1 phrase courte, ex: "essaie gratuitement, lien en bio")

Reponds UNIQUEMENT en JSON valide, sans markdown, sans backticks, format :
{"hook": "...", "probleme": "...", "demo": "...", "cta": "...", "duree_estimee_s": 18}
"""


def generate_script(model, angle: str) -> dict:
    prompt = f"{SYSTEM_PROMPT}\n\nAngle : {angle}"
    response = model.generate_content(prompt)
    text = response.text.strip()
    # Sécurité : au cas où le modèle ajoute des backticks malgré la consigne
    text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        data = {"raw": text, "error": "JSON invalide, voir champ raw"}
    data["angle"] = angle
    return data


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=5, help="Nombre de scripts a generer")
    parser.add_argument("--out", type=str, default="output/scripts.json")
    args = parser.parse_args()

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("ERREUR: variable d'environnement GEMINI_API_KEY manquante", file=sys.stderr)
        sys.exit(1)

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.0-flash")

    angles = (ANGLES * ((args.n // len(ANGLES)) + 1))[: args.n]
    scripts = []
    for i, angle in enumerate(angles, 1):
        print(f"[{i}/{len(angles)}] Generation script pour angle: {angle}")
        scripts.append(generate_script(model, angle))

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(scripts, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OK -> {out_path} ({len(scripts)} scripts)")


if __name__ == "__main__":
    main()
