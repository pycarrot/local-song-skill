# local-song — a Claude Code skill

Make an original song with real sung vocals **on your own computer**: no API keys, no subscription, no cost.
Claude interviews you first (genre, mood, story, voice, lyrics), writes the song with you, renders two takes,
checks the sung words by transcription, lets you pick, cleans up the vocal, masters it and makes a karaoke lyric video.

```
you: make me a song
claude: what style? (acoustic bedroom pop / city pop / lo-fi R&B / …) · what mood? · whose voice? · who writes the lyrics?
        … what's it about? language? title?
        → brief + lyrics for your OK → 2 takes → you pick → polished mp3 + lyric video
```

## Install

```bash
git clone https://github.com/pycarrot/local-song-skill ~/.claude/skills/local-song
```
Then ask Claude Code to make a song. On first use the skill runs `scripts/setup.sh`, which builds
[acestep.cpp](https://github.com/ServeurpersoCom/acestep.cpp) and downloads about 6 GB of models into `~/.local-song`.

**Needs:** macOS with Apple Silicon (Metal) or Linux with an NVIDIA GPU / CPU, 16 GB RAM, about 7 GB of free disk,
plus Homebrew (or git, cmake, ffmpeg, uv and whisper.cpp already installed).

## Pipeline

| Step | Tool | Script |
|---|---|---|
| Compose (lyrics + caption → melody, structure as audio codes) | ACE-Step 1.5 LM 0.6B | `generate.sh` |
| Render audio | ACE-Step 1.5 DiT: **hq** = SFT 50 steps, **fast** = turbo 8 steps, lossless 24-bit WAV | `generate.sh` |
| Check sung lyrics, score each take against the lyric | whisper.cpp small (or any whisper model via `WHISPER_MODEL`) | `check_lyrics.sh`, `score_take.py` |
| Vocal clean-up: separate → de-reverb → presence/air EQ, de-ess, compress → remix | audio-separator (MelBand-Roformer, UVR DeEcho-DeReverb) + ffmpeg | `polish.sh` |
| Master (-14 LUFS, -1.5 dBTP before the MP3 encode, 320 kbps) | ffmpeg loudnorm, two-pass | `polish.sh` |
| Karaoke lyric video, 720p: your lyric lines, timed word by word (whisper DTW timestamps aligned to the lyric), Thai and other complex scripts shaped via fribidi (on Linux, non-Thai scripts need `FONT=…`) | Pillow + ffmpeg | `w2lines.py`, `lyricvid.py` |

Rough times on an M4 Mac with 16 GB: compose about 30 s; render about 2 min per take (fast) or about 4 min per take (hq); polish about 3 min.

**Why polish?** Raw diffusion vocals often sound hazy: a reverb wash and smeared highs.
`polish.sh` pulls the vocal out, strips the wash, adds presence (around 3 kHz) and air (9 kHz+), tames sibilance, and makes room for it in the backing track.
The 24-bit output and the SFT model also help: the default 128 kbps MP3 from the renderer audibly dulls the top end.

**Languages.** English comes out clearest. ACE-Step accepts about 50 languages; others are less clear.
For Thai, the skill keeps your Thai lyrics for composing and the video. It has the model sing a romanized copy with stronger guidance (hq install only).
On the test song, Whisper heard 68–84% of the lines this way, against under 10% from the Thai script.

`examples/window-seat/` holds the request and lyrics for the demo song.

## Free disk afterwards
```bash
~/.claude/skills/local-song/scripts/cleanup.sh models   # about 5.5 GB; keep the built tools
~/.claude/skills/local-song/scripts/cleanup.sh all      # remove everything in ~/.local-song
```

## Credits and licences
- [ACE-Step 1.5](https://github.com/ace-step/ACE-Step) (Apache-2.0), with GGUF builds by [Serveurperso](https://huggingface.co/Serveurperso/ACE-Step-1.5-GGUF)
- [acestep.cpp](https://github.com/ServeurpersoCom/acestep.cpp) (MIT)
- [python-audio-separator](https://github.com/nomadkaraoke/python-audio-separator) (MIT), with [UVR](https://github.com/Anjok07/ultimatevocalremovergui) community models
- [whisper.cpp](https://github.com/ggml-org/whisper.cpp) (MIT)

This repo (scripts and skill) is MIT. Check each model's licence before commercial use. Write original lyrics; don't imitate real singers.
