"""
Assemble video demo + voix off + sous-titres karaoke en un MP4 final pret
pour TikTok/Reels : vignette, fondus d'ouverture/fermeture, watermark de
marque -- via moviepy plutot qu'une chaine de filtres ffmpeg construite a la
main. Les bugs recents (crop mal centre, police surdimensionnee, timing
karaoke, video encodee dans un profil illisible sur mobile) venaient tous de
la fragilite de ce genre de filtre -- moviepy orchestre des objets Python
testables individuellement, et ne genere le ffmpeg final que pour le mux.

Usage:
    python 5_assemble.py --video output/video/demo_raw.webm \
                          --audio output/audio/reel_01.mp3 \
                          --subs output/subs/reel_01.json \
                          --out output/final/reel_01.mp4
"""
import argparse
import json
import tempfile
from pathlib import Path
from urllib.parse import urlencode

import numpy as np
from moviepy import (AudioArrayClip, AudioFileClip, CompositeVideoClip, ImageClip,
                     ImageSequenceClip, VideoFileClip)
from moviepy.video.fx import CrossFadeIn, FadeOut, Loop
from moviepy.audio.fx import AudioFadeIn, AudioFadeOut
from PIL import Image, ImageDraw, ImageFont

import audio_gen
import catalog
from caption_render import norm_word, render_caption
from render_js_anim import FPS as ANIM_FPS, parse_spec, render_frames

FADE_DURATION = 0.4
VOICE_TARGET_RMS = 0.12
PROGRESS_HEIGHT = 10
LOOP_S = 0.45
# Duree d'affichage de l'accroche par defaut (sinon : duree de la 1re scene).
HOOK_DEFAULT_S = 2.6
WATERMARK_FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
WATERMARK_TEXT = "opuscv.fr"
# Pattern interrupt : la video "claque" en zoom arriere sur la 1re image,
# puis de petits coups de zoom a chaque mot-cle prononce (rythme visuel).
PUNCH_OPEN_ZOOM = 0.14
PUNCH_OPEN_S = 0.4
PUNCH_KEYWORD_ZOOM = 0.045
PUNCH_KEYWORD_S = 0.3
PUNCH_MIN_GAP_S = 1.2


def punch_times(cues: list[dict], keywords: set[str]) -> list[float]:
    """Instants des mots-cles prononces, espaces d'au moins PUNCH_MIN_GAP_S."""
    times = []
    for cue in cues:
        for w in cue["words"]:
            if norm_word(w["text"]) in keywords and (not times or w["start"] - times[-1] >= PUNCH_MIN_GAP_S):
                times.append(w["start"])
    return times


def punch_zoom(t: float, beats: list[float]) -> float:
    """Facteur de zoom de la video a l'instant t (1 = aucun)."""
    z = 1.0
    if t < PUNCH_OPEN_S:
        z += PUNCH_OPEN_ZOOM * (1 - t / PUNCH_OPEN_S) ** 2
    for b in beats:
        if 0 <= t - b < PUNCH_KEYWORD_S:
            k = (t - b) / PUNCH_KEYWORD_S
            z += PUNCH_KEYWORD_ZOOM * (1 - k) * min(k * 4, 1)
    return z


def apply_punch(video, beats: list[float]):
    def frame(get_frame, t):
        img = get_frame(t)
        z = punch_zoom(t, beats)
        if z <= 1.001:
            return img
        h, w = img.shape[:2]
        cw, ch = int(w / z), int(h / z)
        x, y = (w - cw) // 2, (h - ch) // 2
        return np.array(Image.fromarray(img[y:y + ch, x:x + cw]).resize((w, h), Image.BILINEAR))
    return video.transform(frame)

def make_vignette(size: tuple[int, int]):
    """
    Masque radial (blanc au centre, plus sombre aux bords) precalcule une
    fois, applique a chaque frame par multiplication -- assombrit doucement
    les bords sans assombrir le centre, evite le look "capture d'ecran brute".
    """
    w, h = size
    yy, xx = np.mgrid[0:h, 0:w]
    cx, cy = w / 2, h / 2
    dist = np.sqrt(((xx - cx) / cx) ** 2 + ((yy - cy) / cy) ** 2)
    strength = np.clip(1 - 0.35 * np.clip(dist - 0.6, 0, None), 0.55, 1.0)
    return strength[:, :, None]  # (h, w, 1), broadcast sur les 3 canaux RGB


def make_watermark_clip(duration: float, theme: dict | None = None) -> ImageClip:
    font = ImageFont.truetype(catalog.font_path(theme, "titre") if theme else WATERMARK_FONT, 34)
    dummy = Image.new("RGBA", (10, 10))
    bbox = ImageDraw.Draw(dummy).textbbox((0, 0), WATERMARK_TEXT, font=font, stroke_width=2)
    img = Image.new("RGBA", (bbox[2] - bbox[0] + 8, bbox[3] - bbox[1] + 8), (0, 0, 0, 0))
    ImageDraw.Draw(img).text((4, 4), WATERMARK_TEXT, font=font, fill=(255, 255, 255, 150),
                              stroke_width=2, stroke_fill=(0, 0, 0, 120))
    return ImageClip(np.array(img), duration=duration).with_position((40, 40))


def make_soundtrack(voice: AudioFileClip, duration: float, ambiance_id: str | None,
                    sfx_cues: list[dict]) -> AudioArrayClip:
    """
    Voix + musique d'ambiance (catalog/audio.json, baissee quand la voix parle)
    + effets sonores cales sur le montage (sound_design.py), mixes en numpy,
    puis masterises (audio_gen.master : compression, -14 LUFS, limiteur).
    """
    cfg = audio_gen.audio_config()["musique"]
    n = int(duration * audio_gen.SR)
    voice_arr = voice.to_soundarray(fps=audio_gen.SR)
    voice_mono = voice_arr.mean(axis=1) if voice_arr.ndim == 2 else voice_arr
    voice_mono = np.pad(voice_mono, (0, max(0, n - len(voice_mono))))[:n]
    # Niveau de voix constant d'un reel a l'autre (le TTS varie) : la musique
    # et les effets sont regles par rapport a lui.
    speech = voice_mono[np.abs(voice_mono) > 0.01]
    if speech.size:
        rms = float(np.sqrt(np.mean(speech ** 2)))
        voice_mono = voice_mono * min(max(VOICE_TARGET_RMS / rms, 0.5), 4.0)
    music = audio_gen.load_music(duration, ambiance_id) * cfg["volume"]
    music = audio_gen.duck(music, voice_mono, cfg["baisse_sous_voix"])[:n]
    effects = audio_gen.render_sfx_track(sfx_cues, duration, audio_gen.get_ambiance(ambiance_id))[:n]
    # Mastering : meme volume percu d'un reel a l'autre (-14 LUFS), sans saturation.
    # Sortie stereo a canaux identiques : BS.1770 additionne les canaux (+3 dB),
    # d'ou la cible mono abaissee d'autant pour mesurer -14 LUFS sur le fichier final.
    mix = audio_gen.master(voice_mono + music + effects, audio_gen.TARGET_LUFS - 3.0)
    return AudioArrayClip(np.column_stack([mix, mix]).astype(np.float32), fps=audio_gen.SR)


def make_progress_bar(duration: float, width: int, theme: dict | None) -> ImageClip:
    """
    Fine barre en haut de l'ecran qui se remplit sur toute la duree : on
    voit que la video avance (et qu'elle finit bientot) -> meilleure retention.
    Une barre pleine largeur glisse depuis la gauche : pas de masque a calculer.
    """
    c = (theme or catalog.get_theme(None))["couleurs"]
    left, right = np.array(catalog.hex_to_rgba(c["primaire"])[:3]), np.array(catalog.hex_to_rgba(c["secondaire"])[:3])
    ramp = np.linspace(0, 1, width)[:, None]
    row = (left * (1 - ramp) + right * ramp).astype("uint8")
    bar = np.repeat(row[None, :, :], PROGRESS_HEIGHT, axis=0)
    return ImageClip(bar, duration=duration).with_position(lambda t: (int(-width * (1 - t / duration)), 0))


def make_caption_clips(cues: list[dict], theme: dict | None = None,
                       keywords: set[str] | None = None) -> list[ImageClip]:
    clips = []
    for cue_index, cue in enumerate(cues):
        words = [w["text"] for w in cue["words"]]
        # Derniere cue du reel = l'appel a l'action (cf. prompt de
        # 1_generate_script.py, qui termine toujours sur l'incitation a
        # essayer le produit) : mise en avant distincte du reste des
        # sous-titres pour qu'elle ne se noie pas dans le flux.
        emphasize = cue_index == len(cues) - 1
        for i, w in enumerate(cue["words"]):
            img = render_caption(words, active_index=i, emphasize=emphasize, theme=theme, keywords=keywords)
            dur = max(w["end"] - w["start"], 0.05)
            clip = (
                ImageClip(np.array(img), duration=dur)
                .with_start(w["start"])
                .with_position(("center", 0.82), relative=True)
            )
            clips.append(clip)
    return clips


def parse_overlay(value: str) -> tuple[float, str]:
    """ "3.2:score_ats?from=35&to=92" -> (3.2, "score_ats?from=35&to=92") """
    start, sep, spec = value.partition(":")
    if not sep or not spec:
        raise ValueError(f"--overlay attend DEBUT_S:gabarit[?params], recu '{value}'")
    return float(start), spec


def make_overlay_clips(overlays: list[tuple[float, str]], duration: float, tmp_dir: Path,
                       theme: dict | None = None) -> list:
    """
    Animations HTML/JS (assets/anim/) rendues en PNG transparents et posees
    par-dessus la video a leur instant de debut -- sous les sous-titres,
    pour que ceux-ci restent lisibles.
    """
    clips = []
    for k, (start, spec) in enumerate(overlays):
        if start >= duration:
            print(f"ATTENTION: surimpression '{spec}' a {start}s, apres la fin ({duration:.1f}s) -> ignoree")
            continue
        name, params = parse_spec(spec)
        frames_dir = tmp_dir / f"overlay_{k:02d}"
        render_frames(name, {**catalog.anim_params(theme), **params}, frames_dir)
        clip = ImageSequenceClip(sorted(str(f) for f in frames_dir.glob("*.png")), fps=ANIM_FPS, with_mask=True)
        clip = clip.with_start(start)
        if start + clip.duration > duration:
            clip = clip.with_duration(duration - start)
        clips.append(clip)
    return clips


def assemble(video_path: Path, audio_path: Path, subs_path: Path, out_path: Path,
             overlays: list[tuple[float, str]] | None = None, theme: dict | None = None,
             hook_text: str = "", hook_duration: float = HOOK_DEFAULT_S,
             ambiance_id: str | None = None, sfx_cues: list[dict] | None = None,
             keywords: list[str] | None = None, progress_bar: bool = True, loop_ending: bool = True,
             punch: bool = True):
    """
    theme : catalog/themes.json (sous-titres, animations, watermark, musique).
    hook_text : accroche affichee en grand des la premiere image (assets/anim/hook.html).
    ambiance_id : musique (catalog/audio.json), sinon celle du theme.
    sfx_cues : effets sonores [{"t", "name", ...}] (sound_design.plan_cues).
    keywords : mots-cles colores dans les sous-titres.
    progress_bar / loop_ending : barre de progression, fin raccordee au debut.
    punch : zoom "claque" a l'ouverture et petits coups de zoom sur les mots-cles.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cues = json.loads(subs_path.read_text(encoding="utf-8"))

    audio = AudioFileClip(str(audio_path))
    duration = audio.duration

    video = VideoFileClip(str(video_path))
    # La demo Playwright (souvent ~10s) est plus courte que la voix off
    # (15-20s) : Loop(duration=...) boucle la video jusqu'a couvrir toute la
    # narration au lieu de la tronquer.
    if video.duration < duration:
        video = video.with_effects([Loop(duration=duration)])
    else:
        video = video.subclipped(0, duration)

    vignette_mask = make_vignette(video.size)
    video = video.image_transform(lambda frame: np.clip(frame * vignette_mask, 0, 255).astype("uint8"))
    if punch:
        video = apply_punch(video, punch_times(cues, {norm_word(k) for k in keywords or []}))

    tmp = tempfile.TemporaryDirectory()
    overlays = list(overlays or [])
    if hook_text:
        overlays.insert(0, (0.0, "hook?" + urlencode({"text": hook_text, "dur": f"{min(hook_duration, duration):.2f}"})))
    overlay_clips = make_overlay_clips(overlays, duration, Path(tmp.name), theme)
    layers = [video, make_watermark_clip(duration, theme), *overlay_clips,
              *make_caption_clips(cues, theme, {norm_word(k) for k in keywords or []})]
    if progress_bar:
        layers.append(make_progress_bar(duration, video.size[0], theme))
    final = CompositeVideoClip(layers, size=video.size).with_duration(duration)

    # Pas de fondu d'ouverture : la premiere image est celle qui s'affiche
    # dans le flux et decide du scroll -- elle doit etre pleine, pas noire.
    # Pas de fondu au noir a la fin non plus : les dernieres images se fondent
    # dans la toute premiere (accroche comprise), la video "boucle" sans
    # coupure visible -> revisionnages, que les algorithmes valorisent.
    if loop_ending and duration > LOOP_S * 4:
        first = ImageClip(final.get_frame(0.1)).with_start(duration - LOOP_S).with_duration(LOOP_S)
        final = CompositeVideoClip([final, first.with_effects([CrossFadeIn(LOOP_S)])],
                                   size=video.size).with_duration(duration)
    else:
        final = final.with_effects([FadeOut(FADE_DURATION)])
    ambiance = ambiance_id or (theme or {}).get("ambiance")
    mixed_audio = make_soundtrack(audio, duration, ambiance, sfx_cues or []).with_duration(duration).with_effects(
        # Fondu d'entree minimal (anti-clic) : la voix demarre des la 1re image.
        [AudioFadeIn(0.05), AudioFadeOut(FADE_DURATION)]
    )
    final = final.with_audio(mixed_audio)

    final.write_videofile(
        str(out_path),
        fps=25,
        codec="libx264",
        audio_codec="aac",
        preset="medium",
        # pix_fmt yuv420p explicite : sans ca, un encodage derive du filtre
        # precedent peut finir dans un profil (ex: yuv444p) que la plupart
        # des lecteurs mobiles ne decodent pas -- video muette a l'usage.
        ffmpeg_params=["-crf", "18", "-pix_fmt", "yuv420p", "-movflags", "+faststart"],
        logger=None,
    )
    video.close()
    audio.close()
    tmp.cleanup()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", type=str, required=True)
    parser.add_argument("--audio", type=str, required=True)
    parser.add_argument("--subs", type=str, required=True)
    parser.add_argument("--out", type=str, required=True)
    parser.add_argument("--overlay", action="append", default=[], metavar="DEBUT_S:GABARIT[?PARAMS]",
                         help="Animation HTML/JS (assets/anim/) en surimpression a partir de DEBUT_S, "
                              "ex: 3.2:score_ats?from=35&to=92 ; repetable")
    parser.add_argument("--theme", type=str, default=None, help="Theme visuel (catalog/themes.json)")
    parser.add_argument("--hook-text", type=str, default="",
                         help="Accroche affichee en grand des la premiere image (vide = aucune)")
    parser.add_argument("--hook-duration", type=float, default=HOOK_DEFAULT_S,
                         help="Duree d'affichage de l'accroche, en s")
    parser.add_argument("--ambiance", type=str, default=None,
                         help="Ambiance musicale (catalog/audio.json), sinon celle du theme")
    parser.add_argument("--sfx", type=str, default=None,
                         help="Fichier JSON des effets sonores (ecrit par run_pipeline.py)")
    parser.add_argument("--keywords", type=str, default="",
                         help="Mots-cles colores dans les sous-titres, separes par |")
    parser.add_argument("--no-progress-bar", action="store_true", help="Sans barre de progression")
    parser.add_argument("--no-loop", action="store_true",
                         help="Fin en fondu au noir au lieu d'un raccord avec la premiere image")
    parser.add_argument("--no-punch", action="store_true",
                         help="Sans zoom 'claque' a l'ouverture ni coups de zoom sur les mots-cles")
    parser.add_argument("--force", action="store_true",
                         help="Reassemble meme si --out existe deja")
    args = parser.parse_args()

    if not args.force and Path(args.out).exists():
        print(f"REPRISE: {args.out} existe deja, on saute (--force pour reassembler)")
        return

    assemble(Path(args.video), Path(args.audio), Path(args.subs), Path(args.out),
             overlays=[parse_overlay(v) for v in args.overlay],
             theme=catalog.get_theme(args.theme) if args.theme else None,
             hook_text=args.hook_text, hook_duration=args.hook_duration, ambiance_id=args.ambiance,
             sfx_cues=json.loads(Path(args.sfx).read_text(encoding="utf-8")) if args.sfx else [],
             keywords=[k for k in args.keywords.split("|") if k.strip()],
             progress_bar=not args.no_progress_bar, loop_ending=not args.no_loop, punch=not args.no_punch)
    print(f"OK -> {args.out}")


if __name__ == "__main__":
    main()
