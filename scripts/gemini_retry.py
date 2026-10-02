"""
Appels Gemini robustes aux surcharges passageres (503 UNAVAILABLE "high demand",
429 quota par minute, 500/502/504) : on attend puis on reessaie, au lieu de faire
echouer tout le run CI sur un pic de charge cote Google.

    response = generate_with_retry(client, model=..., contents=..., config=...,
                                   fallback_model="gemini-2.5-flash")

Attentes : 15, 30, 60, 90 s (~3 min 15 au total). Si `fallback_model` est
donne, les deux derniers essais passent sur ce modele (autre pool de capacite).
Toute autre erreur (cle invalide, requete refusee...) remonte immediatement.
"""
import time

RETRY_CODES = {429, 500, 502, 503, 504}
WAITS = (15, 30, 60, 90)


def _code(exc: Exception) -> int | None:
    code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
    try:
        return int(code)
    except (TypeError, ValueError):
        return None


def generate_with_retry(client, *, model: str, fallback_model: str | None = None, label: str = "Gemini", **kwargs):
    attempts = len(WAITS) + 1
    for n in range(attempts):
        current = fallback_model if fallback_model and n >= attempts - 2 else model
        try:
            return client.models.generate_content(model=current, **kwargs)
        except Exception as exc:  # google.genai.errors.APIError et derivees
            code = _code(exc)
            if code not in RETRY_CODES or n == attempts - 1:
                raise
            wait = WAITS[n]
            nxt = fallback_model if fallback_model and n + 1 >= attempts - 2 else model
            print(f"    {label} indisponible ({code}, {current}) : nouvel essai dans {wait} s"
                  f"{' avec ' + nxt if nxt != current else ''} ({n + 2}/{attempts})", flush=True)
            time.sleep(wait)
