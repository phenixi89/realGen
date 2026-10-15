"""
Contrôle de non-régression (CI) : construit le prompt d'écriture de CHAQUE format du catalogue, avec et sans captures,
en sérieux et en humour, sans appeler Gemini. Un nom de variable utilisé avant sa définition dans build_prompt
(run 80 : « dessin ») passe `py_compile` mais plante le premier lancement : ce script le fait échouer ici.

    python scripts/verif_prompts.py
"""
import importlib.util
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import catalog  # noqa: E402

_spec = importlib.util.spec_from_file_location("generate_script", Path(__file__).resolve().parent / "1_generate_script.py")
gs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gs)


def main() -> int:
    sujets, hooks = catalog.sujets(), catalog.hooks()
    construits, echecs = 0, []
    for fmt in catalog.formats():
        compatibles = [s for s in sujets if s["categorie"] == fmt["categorie"] and set(fmt.get("sujets", [])) & set(s.get("tags", []))]
        if not compatibles:
            echecs.append(f"{fmt['id']} : aucun sujet compatible")
            continue
        pleines = [False] if fmt["cartes"] == "aucune" or fmt.get("dessin") or fmt.get("jeu") else [False, True]
        for sans_captures in pleines:
            for registre in ("serieux", "humour"):
                if registre not in (fmt.get("registres") or ["serieux"]):
                    continue
                hook = next(h for h in hooks if registre in (h.get("registres") or ["serieux"]))
                plan = {"format": fmt, "sujet": compatibles[0], "hook": hook, "registre": registre,
                        "sans_captures": sans_captures, "episode": 1, "cta": "Teste ton CV gratuitement"}
                try:
                    prompt = gs.build_prompt(plan, 25, None, None, [])
                    assert prompt.strip(), "prompt vide"
                    if not (fmt.get("dessin") or fmt.get("jeu")):
                        assert "VÉRITÉ ET COHÉRENCE" in prompt, "COHERENCE_RULE absente du prompt"
                    construits += 1
                except Exception as e:  # noqa: BLE001
                    echecs.append(f"{fmt['id']} (sans_captures={sans_captures}, {registre}) : {type(e).__name__} : {e}")
    for e in echecs:
        print("ECHEC", e)
    print(f"{construits} prompt(s) construit(s), {len(echecs)} échec(s)")
    return 1 if echecs else 0


if __name__ == "__main__":
    sys.exit(main())
