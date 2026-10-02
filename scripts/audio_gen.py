"""
Audio des reels, synthetise (aucune question de droits) : musique d'ambiance
rythmee et effets sonores cales sur le montage ; seuls les bruitages d'animaux
du dessin anime (miaou, ronron) sont des enregistrements CC0 (assets/sfx/). Tout se regle dans catalog/audio.json (ambiances, volumes, regles
anti-abus des effets).

    music(duration, ambiance)      -> nappe + accords + basse + batterie en boucle
    sfx(name, **kw)                -> un effet (whoosh, pop, ding, buzz, riser...)
    render_sfx_track(cues, duration) -> piste d'effets mixee, cues filtres par
                                        les regles (ecart minimal, densite max)
    duck(music, voice)             -> baisse la musique quand la voix parle
    master(mix)                    -> compression douce + normalisation -14 LUFS
                                      + limiteur (niveau standard TikTok/Reels)

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
    if name == "feutre":  # feutre sur papier : quelques traits frottes, doux (dessins, annotations)
        n = int(kw.get("duration", 0.8) * SR)
        rng = np.random.default_rng(seed)
        y, pos = np.zeros(n), 0
        while pos < n:
            length = int(rng.uniform(0.12, 0.28) * SR)
            seg = _noise(length, seed + pos)
            seg = _lowpass_fast(seg, 5500) - _lowpass_fast(seg, 1600)  # bande 1.6-5.5 kHz : frottement
            grain = 0.65 + 0.35 * np.sin(2 * np.pi * rng.uniform(16, 28) * np.arange(length) / SR)
            seg = seg * grain * np.sin(np.linspace(0, np.pi, length)) ** 0.8
            end = min(pos + length, n)
            y[pos:end] += seg[: end - pos]
            pos += length + int(rng.uniform(0.05, 0.14) * SR)
        return _norm(y)
    # --- Bruitages du dessin anime (assets/anim/scene.html, instants donnes par le moteur) ---
    if name == "pas":  # pas feutre : petit choc sourd + frottement
        t = _t(0.12)
        f0 = 95 + 18 * (seed % 3)
        thump = np.sin(2 * np.pi * f0 * t) * env(len(t), 0.002, 0.03)
        scuff = _lowpass_fast(_noise(len(t), seed), 1400, passes=2) * env(len(t), 0.004, 0.04)
        return _norm(thump + 0.7 * scuff)
    if name == "saut":  # petit "hop" qui monte
        t = _t(0.16)
        f = np.linspace(260, 620, len(t))
        return _norm(np.sin(2 * np.pi * np.cumsum(f) / SR) * env(len(t), 0.005, 0.06))
    if name == "chaise":  # chaise : bois qui craque doucement
        n = int(0.32 * SR)
        x = _noise(n, seed)
        band = _lowpass_fast(x, 1800) - _lowpass_fast(x, 450)
        grain = 0.5 + 0.5 * np.sign(np.sin(2 * np.pi * 34 * np.arange(n) / SR))
        return _norm(band * grain * env(n, 0.02, 0.12))
    if name == "pose":  # objet pose sur une table : "toc" de ceramique
        t = _t(0.18)
        body = np.sin(2 * np.pi * 620 * t) + 0.5 * np.sin(2 * np.pi * 1490 * t)
        tap = _lowpass_fast(_noise(len(t), seed), 3500) * env(len(t), 0.0005, 0.01)
        return _norm(body * env(len(t), 0.001, 0.045) + 0.6 * tap)
    if name == "vibreur":  # telephone en vibreur : bourdonnements de 0,3 s
        d = kw.get("duration", 1.2)
        t = _t(d)
        gate = ((t % 0.5) < 0.3).astype(float)
        buzz = np.sign(np.sin(2 * np.pi * 155 * t)) * (0.6 + 0.4 * np.sin(2 * np.pi * 31 * t))
        return _norm(_lowpass_fast(buzz * gate, 900, passes=2))
    if name == "clavier":  # frappe au clavier : rafale de petites touches
        d = kw.get("duration", 1.6)
        y = np.zeros(int(d * SR))
        rng = np.random.default_rng(seed)
        pos = 0
        while pos < len(y):
            k = sfx("click", seed=int(rng.integers(0, 1000)))
            end = min(pos + len(k), len(y))
            y[pos:end] += k[: end - pos] * rng.uniform(0.5, 1.0)
            pos += int(rng.uniform(0.07, 0.16) * SR)
        return _norm(y)
    if name == "idee":  # ampoule qui s'allume : deux notes qui montent
        t = _t(0.45)
        y = np.zeros(len(t))
        for k, note in enumerate((86, 93)):
            start = int(k * 0.09 * SR)
            seg = t[: len(t) - start]
            y[start:] += np.sin(2 * np.pi * midi_hz(note) * seg) * env(len(seg), 0.002, 0.14)
        return _norm(y)
    if name in SAMPLES:  # enregistrements CC0 (assets/sfx/LICENCES.md)
        x = _sample(SAMPLES[name])
        d = kw.get("duration")
        if d and name == "ronron":  # boucle sur la duree demandee, fondu de sortie
            x = np.tile(x, int(np.ceil(d * SR / len(x))))[: int(d * SR)]
            fade = min(len(x), int(0.4 * SR))
            x[-fade:] *= np.linspace(1, 0, fade)
        return _norm(x)
    raise ValueError(f"effet inconnu : {name}")


SFX_DIR = ROOT / "assets" / "sfx"
SAMPLES = {"miaou": "miaou.ogg", "ronron": "ronron.ogg"}
_SAMPLE_CACHE: dict[str, np.ndarray] = {}


def _sample(filename: str) -> np.ndarray:
    """Fichier de assets/sfx/ -> mono SR Hz (decode par ffmpeg, deja requis par le pipeline)."""
    if filename not in _SAMPLE_CACHE:
        import subprocess
        raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(SFX_DIR / filename), "-f", "f32le",
                              "-ac", "1", "-ar", str(SR), "-"], check=True, capture_output=True).stdout
        _SAMPLE_CACHE[filename] = np.frombuffer(raw, dtype=np.float32).astype(np.float64)
    return _SAMPLE_CACHE[filename].copy()


def _norm(x: np.ndarray) -> np.ndarray:
    peak = np.max(np.abs(x)) or 1.0
    return (x / peak).astype(np.float64)


TONAL_SFX = ("pop", "ding", "sparkle", "tick", "idee")


def _pitch(x: np.ndarray, semitones: float) -> np.ndarray:
    """Transpose un effet court par reechantillonnage (duree changee, sans importance ici)."""
    if not semitones:
        return x
    factor = 2 ** (semitones / 12)
    idx = np.arange(0, len(x) - 1, factor)
    return np.interp(idx, np.arange(len(x)), x)


def render_sfx_track(cues: list[dict], duration: float, ambiance: dict | None = None) -> np.ndarray:
    """
    cues : [{"t": 1.2, "name": "pop", "gain": 0.5, ...}] -> piste mono.
    Regles anti-abus (catalog/audio.json "effets") : ecart minimal entre deux
    effets (les frappes de clavier exceptees), nombre maximal par tranche de
    10 s, volume global plafonne. ambiance : profil d'effets de l'ambiance
    musicale ("effets": {"volume": 0.8, "tonalite": -3, "transition": "pop"}) --
    effets plus doux en lo-fi, plus nets en tech, accordes sur la musique.
    """
    profile = (ambiance or {}).get("effets", {})
    rules = audio_config()["effets"]
    if not rules.get("actif", True):
        return np.zeros(int(duration * SR))
    track = np.zeros(int(duration * SR) + SR)
    kept, last = [], -10.0
    # Bruitages du dessin anime (pas, miaou...) : lies a une action visible, hors regles
    # anti-abus ; seul un meme bruitage trop rapproche de lui-meme est ecarte.
    bruitages, last_bruitage = set(rules.get("bruitages", [])), {}
    for cue in sorted(cues, key=lambda c: c["t"]):
        if cue.get("transition") and profile.get("transition"):
            cue = {**cue, "name": profile["transition"]}
        if cue["name"] in rules.get("bannis", []):
            continue
        if cue["name"] in bruitages:
            if cue["t"] - last_bruitage.get(cue["name"], -10.0) < rules.get("bruitage_ecart_min_s", 0.12):
                continue
            last_bruitage[cue["name"]] = cue["t"]
        elif cue["name"] != "click":
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
        if cue["name"] in TONAL_SFX:
            x = _pitch(x, profile.get("tonalite", 0))
        x = x * base * cue.get("gain", 1.0) * rules["volume_global"] * profile.get("volume", 1.0)
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
    if kind == "clap":
        n = int(0.18 * SR)
        x = _noise(n, seed)
        x = x - _lowpass_fast(x, 900)
        e = np.zeros(n)
        for off in (0, int(0.012 * SR), int(0.024 * SR)):
            e[off:] = np.maximum(e[off:], env(n - off, 0.0005, 0.02 if off < int(0.02 * SR) else 0.06))
        return _lowpass_fast(x, 7000) * e
    if kind == "shaker":
        n = int(0.09 * SR)
        x = _noise(n, seed)
        return (x - _lowpass_fast(x, 5000)) * env(n, 0.02, 0.025)
    if kind == "hat":
        n = int(0.06 * SR)
        x = _noise(n, seed)
        return (x - _lowpass_fast(x, 6000)) * env(n, 0.0005, 0.015)
    raise ValueError(kind)


def _voice_chord(chord: list[int], t_bar: np.ndarray, bar: float, step: float, ambiance: dict) -> np.ndarray:
    """
    Accords selon l'instrument de l'ambiance ("instrument") :
      nappe : sinus doux tenus (defaut)      piano : notes frappees, harmoniques qui s'eteignent
      pluck : arpege pince (guitare/kalimba) synth : dents de scie desaccordees (synthwave)
    "arpege" : ordre des notes jouees a chaque double-croche (piano/pluck), ex "0121".
    """
    kind = ambiance.get("instrument", "nappe")
    n = len(t_bar)
    seg = np.zeros(n)
    if kind in ("piano", "pluck"):
        arp = ambiance.get("arpege", "0123" if kind == "pluck" else "0.1.2.1.")
        hits = [(i, int(c)) for i, c in enumerate((arp * 16)[:16]) if c.isdigit()]
        for i, k in hits:
            note = chord[k % len(chord)] + (12 if k >= len(chord) else 0)
            f = midi_hz(note)
            s = int(i * step * SR)
            if s >= n:
                continue
            tt = t_bar[: n - s]
            if kind == "piano":
                tone = (np.sin(2 * np.pi * f * tt) + 0.5 * np.sin(4 * np.pi * f * tt) * np.exp(-tt * 6)
                        + 0.2 * np.sin(6 * np.pi * f * tt) * np.exp(-tt * 9)) * env(len(tt), 0.004, 0.9)
            else:
                tone = (np.sign(np.sin(2 * np.pi * f * tt)) * 0.3 + np.sin(2 * np.pi * f * tt)) * env(len(tt), 0.002, 0.22)
            seg[s:] += tone
        # tapis tres discret des accords tenus pour lier les notes
        for note in chord:
            seg += 0.25 * np.sin(2 * np.pi * midi_hz(note) * t_bar) * env(n, 0.3, bar)
        return seg
    for note in chord:
        f = midi_hz(note)
        if kind == "synth":
            for det in (-0.12, 0.12):
                ph = (f * (1 + det / 100 * 12) * t_bar) % 1.0
                seg += 0.5 * (2 * ph - 1)
        else:
            seg += np.sin(2 * np.pi * f * t_bar) + 0.25 * np.sin(4 * np.pi * f * t_bar)
    return seg * (0.5 + 0.5 * env(n, 0.08, bar * 0.9))


def _bass(chord: list[int], t_bar: np.ndarray, step: float, ambiance: dict) -> np.ndarray:
    """Basse : "pulse" (defaut, pulsee a la noire), "808" (longue, glissee), "douce" (tenue)."""
    f = midi_hz(chord[0] - 12)
    kind = ambiance.get("basse_type", "pulse")
    if kind == "808":
        out = np.zeros(len(t_bar))
        for beat in (0, 6, 10):
            s = int(beat * step * SR)
            tt = t_bar[: len(t_bar) - s]
            ff = f * (1 + 0.5 * np.exp(-tt * 30))
            out[s:] += np.tanh(1.8 * np.sin(2 * np.pi * np.cumsum(ff) / SR)) * env(len(tt), 0.002, 0.5)
        return out
    if kind == "douce":
        return np.sin(2 * np.pi * f * t_bar) * 0.7
    return np.sin(2 * np.pi * f * t_bar) * (0.6 + 0.4 * np.sign(np.sin(2 * np.pi * t_bar / (step * 4))))


def music(duration: float, ambiance: dict, seed: int = 0) -> np.ndarray:
    """
    Boucle synthetisee : accords (instrument de l'ambiance, cf. _voice_chord),
    basse (_bass), batterie selon les motifs 16 pas de l'ambiance
    ("x" = coup, "." = silence ; kick, snare, hat, clap, shaker). -> mono, normalise.
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
        seg = _voice_chord(chord, t_bar, bar, step, ambiance)
        bass = _bass(chord, t_bar, step, ambiance)
        end = min(start + len(t_bar), n)
        out[start:end] += (0.18 * seg / len(chord) + ambiance.get("basse", 0.25) * bass)[: end - start]
        for kind, pattern in ambiance.get("batterie", {}).items():
            hit = _drum(kind, seed + b)
            gain = {"kick": 0.9, "snare": 0.5, "hat": 0.25, "clap": 0.45, "shaker": 0.18}[kind]
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


# ---------------------------------------------------------------------------
# Mastering : compression douce, loudness (ITU-R BS.1770), limiteur
# ---------------------------------------------------------------------------

TARGET_LUFS = -14.0   # niveau de reference TikTok / Instagram / YouTube
CEILING = 10 ** (-1.0 / 20)  # plafond -1 dBFS


def _k_weight(x: np.ndarray) -> np.ndarray:
    """Ponderation K (BS.1770) appliquee en frequentiel : shelf +4 dB aigus, coupe-bas 38 Hz."""
    spec = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    shelf = 1 + (10 ** (4 / 20) - 1) / (1 + (1681.0 / np.maximum(f, 1e-3)) ** 2)
    highpass = 1 / np.sqrt(1 + (38.0 / np.maximum(f, 1e-3)) ** 4)
    return np.fft.irfft(spec * shelf * highpass, len(x))


def loudness(x: np.ndarray) -> float:
    """Loudness integree (LUFS, mono) : blocs de 400 ms, portes absolue -70 et relative -10."""
    y = _k_weight(x)
    block, hop = int(0.4 * SR), int(0.1 * SR)
    if len(y) < block:
        return -70.0
    power = np.array([np.mean(y[i:i + block] ** 2) for i in range(0, len(y) - block + 1, hop)])
    lufs = -0.691 + 10 * np.log10(np.maximum(power, 1e-12))
    gated = power[lufs > -70]
    if not gated.size:
        return -70.0
    rel = -0.691 + 10 * np.log10(np.mean(gated)) - 10
    gated = power[(lufs > -70) & (lufs > rel)]
    return float(-0.691 + 10 * np.log10(np.mean(gated))) if gated.size else -70.0


def _envelope(x: np.ndarray, window_s: float) -> np.ndarray:
    w = max(1, int(window_s * SR))
    return np.sqrt(np.convolve(x ** 2, np.ones(w) / w, mode="same"))


def master(mix: np.ndarray, target_lufs: float = TARGET_LUFS) -> np.ndarray:
    """
    Compression douce (ratio 2:1 au-dessus de -18 dBFS RMS) -> gain vers la
    loudness cible -> limiteur a -1 dBFS. Tous les reels sortent au meme
    volume percu, sans pic qui sature.
    """
    level = 20 * np.log10(np.maximum(_envelope(mix, 0.05), 1e-6))
    over = np.maximum(level + 18, 0)
    gain = 10 ** (-over * 0.5 / 20)
    gain = np.convolve(gain, np.ones(int(0.02 * SR)) / int(0.02 * SR), mode="same")
    x = mix * gain
    current = loudness(x)
    if current > -70:
        x = x * 10 ** ((target_lufs - current) / 20)
    peak = _envelope(x, 0.002) * 1.414
    lim = np.minimum(1.0, CEILING / np.maximum(peak, 1e-9))
    lim = -np.convolve(-lim, np.ones(int(0.004 * SR)) / int(0.004 * SR), mode="same")
    x = x * np.minimum(lim, 1.0)
    return np.clip(x, -CEILING, CEILING)


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
