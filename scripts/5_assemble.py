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
from pathlib import Path

import numpy as np
from moviepy import AudioArrayClip, AudioFileClip, CompositeAudioClip, CompositeVideoClip, ImageClip, VideoFileClip
from moviepy.video.fx import FadeIn, FadeOut, Loop
from moviepy.audio.fx import AudioFadeIn, AudioFadeOut
from PIL import Image, ImageDraw, ImageFont

from caption_render import render_caption

FADE_DURATION = 0.4
WATERMARK_FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
WATERMARK_TEXT = "OpusCV"

# Fond musical genere (pas de fichier externe -> aucune question de licence).
# Nappe Am7 (A2/C3/E3/G3) : neutre et pro, ne tire l'attention sur aucune
# note en particulier -- reste discret sous la voix.
MUSIC_SAMPLE_RATE = 44100
MUSIC_FREQS = [110.00, 130.81, 164.81, 196.00]
MUSIC_GAIN = 0.10  # sous la voix : presence audible mais jamais genante


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


def make_watermark_clip(duration: float) -> ImageClip:
    font = ImageFont.truetype(WATERMARK_FONT, 34)
    dummy = Image.new("RGBA", (10, 10))
    bbox = ImageDraw.Draw(dummy).textbbox((0, 0), WATERMARK_TEXT, font=font, stroke_width=2)
    img = Image.new("RGBA", (bbox[2] - bbox[0] + 8, bbox[3] - bbox[1] + 8), (0, 0, 0, 0))
    ImageDraw.Draw(img).text((4, 4), WATERMARK_TEXT, font=font, fill=(255, 255, 255, 150),
                              stroke_width=2, stroke_fill=(0, 0, 0, 120))
    return ImageClip(np.array(img), duration=duration).with_position((40, 40))


def make_background_music(duration: float) -> AudioArrayClip:
    """
    Nappe synthetisee (4 oscillateurs detunes + vibrato lent + swell
    d'amplitude), volume fixe et bas : juste de quoi eviter un silence
    "capture d'ecran" sans jamais concurrencer la voix off.
    """
    n_samples = int(duration * MUSIC_SAMPLE_RATE)
    t = np.linspace(0, duration, n_samples, endpoint=False)
    signal = np.zeros(n_samples)
    for freq in MUSIC_FREQS:
        vibrato = 1 + 0.002 * np.sin(2 * np.pi * 0.15 * t)
        signal += np.sin(2 * np.pi * freq * vibrato * t)
    signal /= len(MUSIC_FREQS)
    swell = 0.6 + 0.4 * np.sin(2 * np.pi * t / 8.0 - np.pi / 2) ** 2  # respire sur ~8s, pas statique
    signal = signal * swell * MUSIC_GAIN
    stereo = np.column_stack([signal, signal]).astype(np.float32)
    return AudioArrayClip(stereo, fps=MUSIC_SAMPLE_RATE)


def make_caption_clips(cues: list[dict]) -> list[ImageClip]:
    clips = []
    for cue_index, cue in enumerate(cues):
        words = [w["text"] for w in cue["words"]]
        # Derniere cue du reel = l'appel a l'action (cf. prompt de
        # 1_generate_script.py, qui termine toujours sur l'incitation a
        # essayer le produit) : mise en avant distincte du reste des
        # sous-titres pour qu'elle ne se noie pas dans le flux.
        emphasize = cue_index == len(cues) - 1
        for i, w in enumerate(cue["words"]):
            img = render_caption(words, active_index=i, emphasize=emphasize)
            dur = max(w["end"] - w["start"], 0.05)
            clip = (
                ImageClip(np.array(img), duration=dur)
                .with_start(w["start"])
                .with_position(("center", 0.82), relative=True)
            )
            clips.append(clip)
    return clips


def assemble(video_path: Path, audio_path: Path, subs_path: Path, out_path: Path):
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

    layers = [video, make_watermark_clip(duration), *make_caption_clips(cues)]
    final = CompositeVideoClip(layers, size=video.size).with_duration(duration)

    final = final.with_effects([FadeIn(FADE_DURATION), FadeOut(FADE_DURATION)])
    music = make_background_music(duration)
    mixed_audio = CompositeAudioClip([music, audio]).with_duration(duration).with_effects(
        [AudioFadeIn(FADE_DURATION), AudioFadeOut(FADE_DURATION)]
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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", type=str, required=True)
    parser.add_argument("--audio", type=str, required=True)
    parser.add_argument("--subs", type=str, required=True)
    parser.add_argument("--out", type=str, required=True)
    parser.add_argument("--force", action="store_true",
                         help="Reassemble meme si --out existe deja")
    args = parser.parse_args()

    if not args.force and Path(args.out).exists():
        print(f"REPRISE: {args.out} existe deja, on saute (--force pour reassembler)")
        return

    assemble(Path(args.video), Path(args.audio), Path(args.subs), Path(args.out))
    print(f"OK -> {args.out}")


if __name__ == "__main__":
    main()
