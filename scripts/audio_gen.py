"""
Audio des reels, 100 % synthetise (aucun fichier externe -> aucune question
de droits) : musique d'ambiance rythmee et effets sonores cales sur le
montage. Tout se regle dans catalog/audio.json (ambiances, volumes, regles
anti-abus des effets).

    music(duration, ambiance)      -> nappe + accords + basse + batterie en boucle
    sfx(name, **kw)                -> un effet (whoosh, pop, ding, buzz, riser...)
    render_sfx_track(cues, duration) -> piste d'effets mixee, cues filtres par
                                        les regles (ecart minimal, densite max)
    duck(music, voice)             -> baisse la musique quand la voix parle

Si assets/music/<ambiance>/ contient des fichiers audio (morceaux libres de
droits que tu y deposes), l'un d'eux remplace la musique synthetisee.

Usage (ecoute d'une ambiance ou d'un effet) :
    python audio_gen.py --ambiance lofi_chill --duration 20 --out /tmp/a.wav
    python audio_gen.py --sfx whoosh --out /tmp/w.wav
"""
import argparse
import json
import random
import wave
from pathlib import Path

import numpy as np

SR = 44100
ROOT = Path(__file__).resolve().parent.parent
MUSIC_DIR = ROOT / "assets" / "music"
AUDIO_EXT = (".mp3", ".wav", ".ogg", ".m4a")


def audio_config() -> dict:
    return json.loads((ROOT / "catalog" / "audio.json").read_text(encoding="utf-8"))


def get_ambiance(aid: str | None) -> dict:
    ambiances = audio_config()["ambiances"]
    for a in ambiances:
        if a["id"] == aid:
            return a
    return ambiances[0]


# ---------------------------------------------------------------------------
# Primitives
# ---------------------------------------------------------------------------

def _t(duration: float) -> np.ndarray:
    return np.arange(int(duration * SR)) / SR


def midi_hz(note: float) -> float:
    return 440.0 * 2 ** ((note - 69) / 12)


def env(n: int, attack: float, release: float) -> np.ndarray:
    """Enveloppe attaque lineaire / decroissance exponentielle, sur n echantillons."""
    e = np.ones(n)
    a = min(int(attack * SR), n)
    if a:
        e[:a] = np.linspace(0, 1, a)
    t = np.arange(n - a) / SR
    e[a:] = np.exp(-t / max(release, 1e-3))
    return e


def _lowpass_fast(x: np.ndarray, cutoff: float, passes: int = 1) -> np.ndarray:
    """Passe-bas approximatif vectorise (moyenne glissante) pour les longues pistes."""
    width = max(1, int(SR / max(cutoff, 1) / 2))
    kernel = np.ones(width) / width
    for _ in range(passes):
        x = np.convolve(x, kernel, mode="same")
    return x


def _noise(n: int, seed: int) -> np.ndarray:
    return np.random.default_rng(seed).uniform(-1, 1, n)


# ---------------------------------------------------------------------------
# Effets sonores
# ---------------------------------------------------------------------------

def sfx(name: str, seed: int = 0, **kw) -> np.ndarray:
    """Un effet sonore mono, normalise ~[-1, 1]."""
    if name == "whoosh":  # souffle filtre qui monte puis retombe (transition)
        d = kw.get("duration", 0.45)
        n = int(d * SR)
        x = _noise(n, seed)
        cut = np.linspace(400, 3500, n // 2).tolist() + np.linspace(3500, 300, n - n // 2).tolist()
        y = np.zeros(n)
        acc = 0.0
        for i in range(n):
            alpha = 1 - np.exp(-2 * np.pi * cut[i] / SR)
            acc += alpha * (x[i] - acc)
            y[i] = acc
        shape = np.sin(np.linspace(0, np.pi, n)) ** 1.5
        return _norm(y * shape)
    if name == "mouse":  # clic de souris (curseur anime) : deux petits "tac" rapproches
        n = int(0.07 * SR)
        y = np.zeros(n)
        for k, off in enumerate((0, int(0.035 * SR))):
            m = int(0.012 * SR)
            y[off:off + m] += _lowpass_fast(_noise(m, seed + k), 4000) * env(m, 0.0003, 0.003)
        return _norm(y)
    if name == "tick":  # transition discrete : petit "tap" boise, feutre
        t = _t(0.09)
        body = np.sin(2 * np.pi * 740 * t) + 0.4 * np.sin(2 * np.pi * 1480 * t)
        tap = _lowpass_fast(_noise(len(t), seed), 2500)
        return _norm((0.8 * body + 0.3 * tap) * env(len(t), 0.001, 0.018))
    if name == "pop":  # petit "bloop" : apparition d'une carte / d'un titre
        t = _t(0.12)
        f = np.linspace(900, 380, len(t))
        return _norm(np.sin(2 * np.pi * np.cumsum(f) / SR) * env(len(t), 0.002, 0.035))
    if name == "click":  # frappe de touche (texte qui se tape)
        n = int(0.03 * SR)
        x = _noise(n, seed) * env(n, 0.0005, 0.006)
        tone = np.sin(2 * np.pi * (1800 + 400 * (seed % 3)) * _t(0.03)[:n]) * env(n, 0.0005, 0.004)
        return _norm(0.6 * x + 0.4 * tone)
    if name == "ding":  # bonne reponse / realite / apres
        t = _t(0.9)
        y = sum(a * np.sin(2 * np.pi * midi_hz(n) * t) for n, a in ((84, 1), (91, .5), (96, .25)))
        return _norm(y * env(len(t), 0.003, 0.28))
    if name == "buzz":  # mauvaise reponse / idee recue (court, pas agressif)
        t = _t(0.28)
        sq = np.sign(np.sin(2 * np.pi * 110 * t)) + 0.5 * np.sign(np.sin(2 * np.pi * 116 * t))
        return _norm(_lowpass_fast(sq, 1200) * env(len(t), 0.005, 0.12))
    if name == "riser":  # montee de tension (suspense)
        d = kw.get("duration", 1.2)
        t = _t(d)
        f = 180 * (8 ** (t / d))
        tone = np.sin(2 * np.pi * np.cumsum(f) / SR)
        noise = _lowpass_fast(_noise(len(t), seed), 2500) * (t / d)
        return _norm((0.6 * tone + 0.8 * noise) * (t / d) ** 1.6)
    if name == "impact":  # revelation / debut percutant
        t = _t(0.9)
        f = 55 * np.exp(-t * 3) + 38
        boom = np.sin(2 * np.pi * np.cumsum(f) / SR) * env(len(t), 0.001, 0.32)
        crack = _lowpass_fast(_noise(len(t), seed), 3000) * env(len(t), 0.0005, 0.05)
        return _norm(boom + 0.5 * crack)
    if name == "sparkle":  # scintillement (CTA)
        t = _t(0.7)
        y = np.zeros(len(t))
        for k, note in enumerate((88, 91, 95, 100)):
            start = int(k * 0.07 * SR)
            seg = t[: len(t) - start]
            y[start:] += np.sin(2 * np.pi * midi_hz(note) * seg) * env(len(seg), 0.002, 0.12)
        return _norm(y)
    raise ValueError(f"effet inconnu : {name}")


def _norm(x: np.ndarray) -> np.ndarray:
    peak = np.max(np.abs(x)) or 1.0
    return (x / peak).astype(np.float64)


def render_sfx_track(cues: list[dict], duration: float) -> np.ndarray:
    """
    cues : [{"t": 1.2, "name": "pop", "gain": 0.5, ...}] -> piste mono.
    Regles anti-abus (catalog/audio.json "effets") : ecart minimal entre deux
    effets (les frappes de clavier exceptees), nombre maximal par tranche de
    10 s, volume global plafonne.
    """
    rules = audio_config()["effets"]
    if not rules.get("actif", True):
        return np.zeros(int(duration * SR))
    track = np.zeros(int(duration * SR) + SR)
    kept, last = [], -10.0
    for cue in sorted(cues, key=lambda c: c["t"]):
        if cue["name"] in rules.get("bannis", []):
            continue
        if cue["name"] != "click":
            if cue["t"] - last < rules["ecart_min_s"]:
                continue
            window = [k for k in kept if k["name"] != "click" and cue["t"] - k["t"] < 10]
            if len(window) >= rules["max_par_10s"]:
                continue
            last = cue["t"]
        kept.append(cue)
    for i, cue in enumerate(kept):
        base = rules["volumes"].get(cue["name"], 0.3)
        x = sfx(cue["name"], seed=i, **{k: v for k, v in cue.items() if k in ("duration",)})
        x = x * base * cue.get("gain", 1.0) * rules["volume_global"]
        start = int(max(cue["t"], 0) * SR)
        end = min(start + len(x), len(track))
        track[start:end] += x[: end - start]
    return track[: int(duration * SR)]


# ---------------------------------------------------------------------------
# Musique
# ---------------------------------------------------------------------------

def _track_file(ambiance_id: str, rng: random.Random) -> Path | None:
    folder = MUSIC_DIR / ambiance_id
    files = sorted(p for p in folder.glob("*") if p.suffix.lower() in AUDIO_EXT) if folder.exists() else []
    return rng.choice(files) if files else None


def _drum(kind: str, seed: int) -> np.ndarray:
    if kind == "kick":
        t = _t(0.35)
        f = 120 * np.exp(-t * 18) + 45
        return np.sin(2 * np.pi * np.cumsum(f) / SR) * env(len(t), 0.001, 0.12)
    if kind == "snare":
        n = int(0.22 * SR)
        return 0.7 * _lowpass_fast(_noise(n, seed), 5000) * env(n, 0.001, 0.07) + \
            0.3 * np.sin(2 * np.pi * 190 * _t(0.22)[:n]) * env(n, 0.001, 0.05)
    if kind == "hat":
        n = int(0.06 * SR)
        x = _noise(n, seed)
        return (x - _lowpass_fast(x, 6000)) * env(n, 0.0005, 0.015)
    raise ValueError(kind)


def music(duration: float, ambiance: dict, seed: int = 0) -> np.ndarray:
    """
    Boucle synthetisee : accords (sinus doux + 2e harmonique), basse sur la
    fondamentale, batterie selon les motifs 16 pas de l'ambiance
    ("x" = coup, "." = silence). -> mono, normalise.
    """
    n = int(duration * SR) + SR
    out = np.zeros(n)
    step = 60 / ambiance["bpm"] / 4  # double-croche
    bar = step * 16
    chords = ambiance["accords"]
    t_bar = _t(bar)
    for b in range(int(duration / bar) + 2):
        chord = chords[b % len(chords)]
        start = int(b * bar * SR)
        if start >= n:
            break
        seg = np.zeros(len(t_bar))
        for note in chord:
            f = midi_hz(note)
            seg += np.sin(2 * np.pi * f * t_bar) + 0.25 * np.sin(4 * np.pi * f * t_bar)
        seg *= 0.5 + 0.5 * env(len(t_bar), 0.08, bar * 0.9)
        bass_f = midi_hz(chord[0] - 12)
        bass = np.sin(2 * np.pi * bass_f * t_bar) * (0.6 + 0.4 * np.sign(np.sin(2 * np.pi * t_bar / (step * 4))))
        end = min(start + len(t_bar), n)
        out[start:end] += (0.18 * seg / len(chord) + ambiance.get("basse", 0.25) * bass)[: end - start]
        for kind, pattern in ambiance.get("batterie", {}).items():
            hit = _drum(kind, seed + b)
            gain = {"kick": 0.9, "snare": 0.5, "hat": 0.25}[kind]
            for i, c in enumerate(pattern):
                if c != "x":
                    continue
                s = start + int(i * step * SR)
                e = min(s + len(hit), n)
                if s < n:
                    out[s:e] += gain * hit[: e - s]
    out = _lowpass_fast(out, ambiance.get("filtre_hz", 6000))
    return _norm(out[: int(duration * SR)])


def load_music(duration: float, ambiance_id: str | None, seed: int = 0) -> np.ndarray:
    """Morceau depose dans assets/music/<ambiance>/ s'il y en a, sinon synthese."""
    ambiance = get_ambiance(ambiance_id)
    path = _track_file(ambiance["id"], random.Random(seed))
    if path:
        from moviepy import AudioFileClip
        clip = AudioFileClip(str(path))
        arr = clip.to_soundarray(fps=SR).mean(axis=1)
        clip.close()
        reps = int(np.ceil(duration * SR / len(arr)))
        return _norm(np.tile(arr, reps)[: int(duration * SR)])
    return music(duration, ambiance, seed)


def duck(music_track: np.ndarray, voice: np.ndarray, amount: float) -> np.ndarray:
    """Musique baissee de `amount` (0-1) quand la voix parle, avec transitions douces."""
    n = min(len(music_track), len(voice))
    level = np.abs(voice[:n])
    level = np.convolve(level, np.ones(int(0.05 * SR)) / int(0.05 * SR), mode="same")
    active = (level > 0.02 * (np.max(level) or 1)).astype(float)
    active = np.convolve(active, np.ones(int(0.25 * SR)) / int(0.25 * SR), mode="same")
    gain = 1 - amount * np.clip(active, 0, 1)
    out = music_track.copy()
    out[:n] *= gain
    return out


def write_wav(path: Path, mono: np.ndarray):
    data = (np.clip(mono, -1, 1) * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(data.tobytes())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ambiance", type=str, default=None)
    parser.add_argument("--sfx", type=str, default=None)
    parser.add_argument("--duration", type=float, default=15)
    parser.add_argument("--out", type=str, required=True)
    args = parser.parse_args()
    x = sfx(args.sfx) if args.sfx else load_music(args.duration, args.ambiance)
    write_wav(Path(args.out), 0.8 * x)
    print(f"OK -> {args.out}")


if __name__ == "__main__":
    main()
