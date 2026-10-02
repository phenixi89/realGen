"""
Controle des voix du dessin anime : Gemini TTS multi-locuteurs fond parfois tout le
dialogue dans UNE voix (run 58 : les repliques de Karim dites avec la voix de Lea).

Chaque replique (instants mesures par Whisper, timeline "repliques") est comparee aux
deux voix du reel : au moins 40 % de ses trames voisees doivent etre plus proches (en
hauteur) de la voix de son personnage que de l'autre. Hauteur de reference d'une voix = mediane mesuree sur ses
enregistrements de CTA (assets/voix_cta/). Non verifiable (accepte) quand les deux voix
ont des hauteurs trop proches (< 25 % d'ecart) ou n'ont pas d'enregistrement.
"""
import subprocess
from pathlib import Path

import numpy as np

SR = 24000
CTA_DIR = Path(__file__).resolve().parent.parent / "assets" / "voix_cta"
SEUIL_PART = 0.4  # run 58 : repliques bien dites >= 49 %, voix confondue <= 25 %
_HAUTEURS: dict[str, float | None] = {}


def pcm(path: Path) -> np.ndarray:
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(path), "-f", "s16le", "-ac", "1",
                          "-ar", str(SR), "-"], check=True, capture_output=True).stdout
    return np.frombuffer(raw, dtype=np.int16).astype(np.float64)


def f0(x: np.ndarray, sr: int = SR) -> np.ndarray:
    """Hauteur (Hz) de chaque trame voisee de 40 ms (autocorrelation) ; trames muettes ou bruitees ecartees."""
    n, hop = int(0.04 * sr), int(0.02 * sr)
    if len(x) < n:
        return np.array([])
    frames = np.lib.stride_tricks.sliding_window_view(x, n)[::hop]
    rms = np.sqrt((frames ** 2).mean(axis=1))
    frames = frames[rms > rms.max() * 0.1]
    spec = np.fft.rfft(frames - frames.mean(axis=1, keepdims=True), 2 * n)
    ac = np.fft.irfft(np.abs(spec) ** 2)[:, :n]
    lo, hi = sr // 400, sr // 70
    k = lo + ac[:, lo:hi].argmax(axis=1)
    nettes = ac[np.arange(len(k)), k] > 0.4 * ac[:, 0]
    return sr / k[nettes]


def hauteur_voix(voice: str) -> float | None:
    if voice not in _HAUTEURS:
        mesures = [f0(pcm(p)) for p in sorted(CTA_DIR.glob(f"{voice}_*.ogg"))]
        tout = np.concatenate(mesures) if mesures else np.array([])
        _HAUTEURS[voice] = float(np.median(tout)) if len(tout) else None
    return _HAUTEURS[voice]


def repliques_bien_dites(audio: Path, timeline: dict, voices: dict[str, str]) -> tuple[bool, str]:
    """(toutes les repliques dites par la voix de leur personnage ?, detail des repliques fautives)."""
    repliques = [r for sc in timeline.get("scenes", []) for r in sc.get("repliques") or [] if r.get("qui") in voices]
    refs = {q: hauteur_voix(voices[q]) for q in dict.fromkeys(r["qui"] for r in repliques)}
    if len(refs) != 2 or None in refs.values() or max(refs.values()) / min(refs.values()) < 1.25:
        return True, "non verifiable"
    x = pcm(audio)
    fautes = []
    for r in repliques:
        h = f0(x[int(r["start"] * SR):int(r["end"] * SR)])
        if len(h) < 10:
            continue
        autre = next(q for q in refs if q != r["qui"])
        # Part des trames plus proches de la voix du personnage que de l'autre : une voix grave
        # emue monte (mediane trompeuse), mais garde la majorite de ses trames de son cote.
        part = float(np.mean(np.abs(np.log(h / refs[r["qui"]])) < np.abs(np.log(h / refs[autre]))))
        if part < SEUIL_PART:
            fautes.append(f"{r['qui']} à {r['start']:.1f} s ({part:.0%} de ses trames)")
    return not fautes, "; ".join(fautes) or "ok"
