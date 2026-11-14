import array
import math
import os
import random
from typing import Dict, List, Optional, Tuple
import pygame


class SoundManager:
    """
    Handles background music and sound effects for BOUNCE BACK.
    Automatically loads custom .ogg/.wav files from a 'sounds/' folder if present,
    and falls back to built-in 16-bit procedural retro audio so sound works right away.
    """

    SAMPLE_RATE: int = 22050

    def __init__(self) -> None:
        self.enabled: bool = True
        self.muted: bool = False
        self.music_started: bool = False
        self.sounds: Dict[str, Optional[pygame.mixer.Sound]] = {}
        self.music_sound: Optional[pygame.mixer.Sound] = None
        self.music_channel: Optional[pygame.mixer.Channel] = None

        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(
                    frequency=self.SAMPLE_RATE,
                    size=-16,
                    channels=1,
                    buffer=512,
                )
            pygame.mixer.set_num_channels(12)
            self.music_channel = pygame.mixer.Channel(0)
            self._load_or_synthesize_all()
        except Exception:
            self.enabled = False

    def _samples_to_sound(self, samples: List[float]) -> pygame.mixer.Sound:
        """Convert normalized float samples (-1.0..1.0) into a 16-bit Pygame Sound."""
        pcm = array.array("h")
        for s in samples:
            clamped = max(-1.0, min(1.0, s))
            pcm.append(int(clamped * 32767))
        return pygame.mixer.Sound(buffer=pcm)

    def _try_load_custom(self, base_name: str) -> Optional[pygame.mixer.Sound]:
        """Check for sounds/<name>.ogg or sounds/<name>.wav on disk."""
        for ext in (".ogg", ".wav"):
            path = os.path.join("sounds", base_name + ext)
            if os.path.exists(path):
                try:
                    return pygame.mixer.Sound(path)
                except Exception:
                    pass
        return None

    def _synth_eat(self, special: bool = False) -> pygame.mixer.Sound:
        """Bright 16-bit sparkle chime when eating a Soul."""
        notes = [659.25, 987.77, 1318.51] if special else [587.33, 880.00]
        note_dur = 0.055
        total_samples = int(self.SAMPLE_RATE * (note_dur * len(notes) + 0.04))
        samples = [0.0] * total_samples

        for idx, freq in enumerate(notes):
            start = int(idx * note_dur * self.SAMPLE_RATE)
            length = int((note_dur + 0.04) * self.SAMPLE_RATE)
            for i in range(length):
                if start + i >= total_samples:
                    break
                t = i / self.SAMPLE_RATE
                env = math.exp(-t * 24.0) * min(1.0, t / 0.004)
                tone = math.sin(math.tau * freq * t) + 0.35 * math.sin(math.tau * freq * 2.0 * t)
                samples[start + i] += tone * env * 0.24

        return self._samples_to_sound(samples)

    def _synth_dash(self) -> pygame.mixer.Sound:
        """Quick airy breeze whoosh for clicking to steer or triggering Wind Gust."""
        dur = 0.14
        total_samples = int(self.SAMPLE_RATE * dur)
        samples = [0.0] * total_samples
        filtered_noise = 0.0

        for i in range(total_samples):
            t = i / self.SAMPLE_RATE
            progress = t / dur
            env = math.sin(progress * math.pi) ** 1.3

            # Soft filtered wind noise + gentle pitch glide
            white = random.uniform(-1.0, 1.0)
            filtered_noise = 0.72 * filtered_noise + 0.28 * white
            sweep_freq = 420.0 - (210.0 * progress)
            breeze_tone = math.sin(math.tau * sweep_freq * t)

            samples[i] = (filtered_noise * 0.65 + breeze_tone * 0.35) * env * 0.26

        return self._samples_to_sound(samples)

    def _synth_upgrade(self) -> pygame.mixer.Sound:
        """Crisp wooden tap + warm coin double-ding for buying upgrades."""
        dur = 0.17
        total_samples = int(self.SAMPLE_RATE * dur)
        samples = [0.0] * total_samples

        for i in range(total_samples):
            t = i / self.SAMPLE_RATE
            # Subtle wooden knock at t=0
            wood_env = math.exp(-t * 70.0)
            wood = math.sin(math.tau * 210.0 * t) * wood_env * 0.25

            # Two-step bright coin ding (B5 -> E6)
            freq = 987.77 if t < 0.065 else 1318.51
            local_t = t if t < 0.065 else (t - 0.065)
            ding_env = math.exp(-local_t * 22.0) * min(1.0, local_t / 0.003)
            ding = math.sin(math.tau * freq * local_t) * ding_env * 0.28

            samples[i] = wood + ding

        return self._samples_to_sound(samples)

    def _synth_rebirth(self) -> pygame.mixer.Sound:
        """Deep mystical cosmic chord swell for Rebirth & Black Hole unlock."""
        dur = 0.68
        total_samples = int(self.SAMPLE_RATE * dur)
        samples = [0.0] * total_samples
        chord = [146.83, 220.00, 293.66, 440.00, 587.33]

        for i in range(total_samples):
            t = i / self.SAMPLE_RATE
            progress = t / dur
            env = math.sin(progress * math.pi) ** 1.1
            shimmer = 1.0 + 0.12 * progress

            val = 0.0
            for idx, base_f in enumerate(chord):
                freq = base_f * shimmer
                val += math.sin(math.tau * freq * t) / (1.0 + idx * 0.35)

            samples[i] = (val / 2.6) * env * 0.34

        return self._samples_to_sound(samples)

    def _synth_forest_music(self) -> pygame.mixer.Sound:
        """Cozy, slightly mysterious 16-bit autumn woods music-box loop."""
        step_dur = 0.36  # Gentle waltz/lullaby tempo
        # (melody_hz, bass_hz) pairs across 32 steps (~11.5s seamless loop)
        pattern: List[Tuple[float, float]] = [
            (293.66, 146.83), (0.0, 0.0), (440.00, 220.00), (523.25, 0.0),
            (587.33, 146.83), (523.25, 0.0), (440.00, 220.00), (349.23, 0.0),
            (392.00, 116.54), (0.0, 0.0), (440.00, 174.61), (523.25, 0.0),
            (440.00, 130.81), (392.00, 0.0), (329.63, 196.00), (0.0, 0.0),
            (293.66, 146.83), (349.23, 0.0), (440.00, 220.00), (587.33, 0.0),
            (659.25, 116.54), (587.33, 0.0), (523.25, 174.61), (440.00, 0.0),
            (392.00, 98.00),  (440.00, 0.0), (349.23, 146.83), (329.63, 0.0),
            (293.66, 146.83), (0.0, 220.00), (293.66, 146.83), (0.0, 0.0),
        ]

        total_samples = int(self.SAMPLE_RATE * step_dur * len(pattern))
        samples = [0.0] * total_samples
        note_len = int(step_dur * 1.45 * self.SAMPLE_RATE)

        for step_idx, (mel_f, bass_f) in enumerate(pattern):
            start = int(step_idx * step_dur * self.SAMPLE_RATE)
            for i in range(note_len):
                pos = start + i
                if pos >= total_samples:
                    break
                t = i / self.SAMPLE_RATE
                attack = min(1.0, t / 0.012)

                if mel_f > 0.0:
                    m_env = math.exp(-t * 4.8) * attack
                    mel = (
                        math.sin(math.tau * mel_f * t)
                        + 0.22 * math.sin(math.tau * mel_f * 2.0 * t)
                    )
                    samples[pos] += mel * m_env * 0.11

                if bass_f > 0.0:
                    b_env = math.exp(-t * 3.2) * attack
                    bass = math.sin(math.tau * bass_f * t)
                    samples[pos] += bass * b_env * 0.10

        return self._samples_to_sound(samples)

    def _load_or_synthesize_all(self) -> None:
        """Load custom files from sounds/ if available, else generate 16-bit audio."""
        eat_snd = self._try_load_custom("eat") or self._synth_eat(special=False)
        eat_snd.set_volume(0.45)
        self.sounds["eat"] = eat_snd

        eat_special_snd = self._try_load_custom("eat_special") or self._synth_eat(special=True)
        eat_special_snd.set_volume(0.55)
        self.sounds["eat_special"] = eat_special_snd

        dash_snd = self._try_load_custom("dash") or self._synth_dash()
        dash_snd.set_volume(0.40)
        self.sounds["dash"] = dash_snd

        upgrade_snd = self._try_load_custom("upgrade") or self._synth_upgrade()
        upgrade_snd.set_volume(0.55)
        self.sounds["upgrade"] = upgrade_snd

        rebirth_snd = self._try_load_custom("rebirth") or self._synth_rebirth()
        rebirth_snd.set_volume(0.70)
        self.sounds["rebirth"] = rebirth_snd

        music_snd = self._try_load_custom("forest_music") or self._synth_forest_music()
        music_snd.set_volume(0.45)
        self.music_sound = music_snd

    def start_music(self) -> None:
        """Start looping the background forest song (safe to call on first user click)."""
        if not self.enabled or self.muted or self.music_sound is None or self.music_channel is None:
            return
        try:
            if not self.music_channel.get_busy():
                self.music_channel.play(self.music_sound, loops=-1)
                self.music_started = True
        except Exception:
            pass

    def toggle_mute(self) -> bool:
        """Mute or unmute all music and sound effects. Returns the new muted state."""
        self.muted = not self.muted
        if not self.enabled:
            return self.muted
        try:
            if self.muted:
                pygame.mixer.pause()
            else:
                if self.music_channel is not None and not self.music_channel.get_busy():
                    self.start_music()
                else:
                    pygame.mixer.unpause()
        except Exception:
            pass
        return self.muted

    def play(self, key: str) -> None:
        """Play a named sound effect ('eat', 'eat_special', 'dash', 'upgrade', 'rebirth')."""
        if not self.enabled or self.muted:
            return
        snd = self.sounds.get(key)
        if snd is not None:
            try:
                snd.play()
            except Exception:
                pass