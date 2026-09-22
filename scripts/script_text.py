"""Texte de narration partage entre 2_generate_voice.py (TTS) et
4_generate_subtitles.py (alignement des sous-titres sur ce texte exact)."""


def script_to_text(script: dict) -> str:
    """Assemble hook/probleme/demo/cta en un seul texte a lire."""
    parts = [script.get("hook", ""), script.get("probleme", ""),
             script.get("demo", ""), script.get("cta", "")]
    return " ".join(p for p in parts if p)
