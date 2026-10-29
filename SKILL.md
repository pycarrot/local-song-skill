---
name: local-song
description: Co-write and produce an original full song with sung vocals entirely on the user's own machine — no API keys, no cost — with ACE-Step 1.5 (acestep.cpp), then clean up the vocal, master it and render a karaoke lyric video. The user shapes the song (genre, mood, story, voice, lyrics) before anything is generated and picks the final take. Use when the user asks to make, write, compose or generate a song, a track with vocals, music in some style, "ทำเพลง", "แต่งเพลง", especially offline or without paid APIs.
---

# Local song studio

You are the producer; the user is the artist. Nothing is generated until the user has approved a song brief and the lyrics, and the user (who can hear — you cannot) picks the take.

Scripts live in `scripts/` next to this file (call them by absolute path). Everything they install goes to `$LS_HOME` (default `~/.local-song`).

## 1. Interview the user (always — this is the point of the skill)

Ask, don't assume. Use your question tool (e.g. AskUserQuestion, up to 4 questions per call) when you have one; otherwise ask in chat. Offer concrete options plus "other", and recommend one. Speak the user's language.

Round 1:
- **Genre / style** — e.g. acoustic bedroom pop, city pop, lo-fi R&B, indie rock, synthwave, Thai luk thung–flavoured pop, ballad with piano. If they name a reference song or artist, translate it into sound words (tempo, instruments, vocal character, mood) — never put artist names or song titles into the generation prompt and never reuse their lyrics or melody.
- **Mood / energy** — tender, nostalgic, hopeful, heartbroken, hype, chill.
- **Voice** — female / male / duet, and character (breathy, warm, powerful, falsetto hook).
- **Lyrics** — "you write them", "we write together" or "I'll give you lyrics".

Round 2 (free text is fine):
- **What is it about?** A story, a person, a place, a memory, a few key phrases they want in it. Personal details make the song theirs.
- **Language** — English is the strongest. `vocal_language` also accepts th, ja, ko, zh, es, fr, de, pt, vi, id and ~40 more; less common languages may come out less clear. Say so honestly.
- **Length and tempo** — default about 3:20, tempo chosen to fit the genre.
- **Title** (or let you propose).

Then quickly check the machine (`df -h ~`, RAM, GPU) and offer quality: **hq** (SFT model, 50 steps, cleaner vocals, about 4 min per take on an M4 Mac) or **fast** (turbo, 8 steps, about 2 min per take, slightly hazy vocals). Both need about 7 GB of free disk.

## 2. Song brief → approval

Write and show:
- the **caption**: one dense paragraph of sound words: genre, instruments, vocal description, mood, production ("clean modern mix, upfront dry lead vocal" helps clarity);
- **bpm, key, time signature, duration, vocal_language**;
- the **lyrics** with section tags: `[Intro - …]`, `[Verse 1]`, `[Pre-Chorus]`, `[Chorus]`, `[Bridge - stripped back]`, `[Final Chorus - full band, harmonies]`, `[Outro - …]`. Short singable lines, a hook repeated in every chorus, three choruses. Original words only.

Ask for changes and iterate until the user says go. When co-writing, build on their lines rather than replacing them.

## 3. Install (first time only)

```bash
scripts/setup.sh hq     # or: fast
```
Clones and builds acestep.cpp (Metal / CUDA / CPU), downloads the models (VAE, text encoder, 0.6B LM, DiT), whisper.cpp small and an audio-separator venv. Run it in the background; it takes a while on first install. If disk is short, tell the user how much is needed and what could be freed; do not delete anything that is not yours without asking.

## 4. Generate two takes

Write the request JSON (see `examples/window-seat/request.json`): `caption`, `lyrics`, `duration`, `bpm`, `keyscale`, `timesignature`, `vocal_language`. Then:
```bash
scripts/generate.sh request.json out/
```
It writes `out/req00.wav` and `out/req10.wav` (two different takes) plus `req0.json`/`req1.json`, which hold each take's audio codes (its melody and structure).

## 5. Check, then let the user choose

For each take run `scripts/check_lyrics.sh out/req00.wav en` and compare with the lyrics: missing sections, garbled lines, wrong words. Report this per take, and send both takes to the user to listen to. **The user picks**, and can ask for:
- **the same take, rendered cleaner**: set `synth_model`/`inference_steps`/`shift` in that `reqN.json` (e.g. SFT, 50, 1.0) and run `scripts/generate.sh --synth-only out/reqN.json`. Melody and structure stay; the sound gets re-rendered;
- **new takes**: change the caption or lyrics and run step 4 again (a new seed is picked each run).

## 6. Polish + master

```bash
scripts/polish.sh out/req10.wav "Song.mp3" [fade_start_s] [vocal_boost_db=1.5]
```
Splits vocal from backing (MelBand-Roformer), strips the reverb wash from the vocal (UVR DeEcho-DeReverb), adds presence and air, de-esses, lightly compresses, carves room in the backing track, then remixes to -14 LUFS / -1 dBTP, 320 kbps. The first run downloads about 1.1 GB of separation models. If the user says the vocal is too quiet or loud, re-run with another boost.

## 7. Lyric video (optional, offer it)

```bash
scripts/check_lyrics.sh Song.mp3 en
python3 scripts/w2lines.py Song.mp3.whisper.json lyrics.txt lines.json
TITLE="song title" TOP=b5a0de BOTTOM=5c488c $LS_HOME/venv/bin/python scripts/lyricvid.py lines.json Song.mp3 "Song (lyric video).mp4"
```
720p karaoke with word-by-word highlighting. Pick gradient colours that fit the song's mood. Grab a frame (`ffmpeg -ss 60 -i … -frames:v 1 f.jpg`) and look at it before sending. For languages without spaces (Thai, Japanese, Chinese) whole lines light up at once.

## 8. Deliver

Give the user the mastered mp3, the other take, the lyrics and the video. State plainly what you checked (lyrics via transcription, loudness) and what you could not (how it sounds). Ask what to change. When they are done, offer `scripts/cleanup.sh models` (frees about 5.5 GB) or `cleanup.sh all`.

## Rules
- Original lyrics only; no imitation of a named singer's voice; no artist names in captions.
- Never run generation before the user approves the brief and lyrics.
- Disk can fill up and swap lives on the same disk, so check `df` before downloads and keep at least 1 GB free while rendering.
