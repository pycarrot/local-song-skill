# whisper.cpp full JSON -> lines.json for lyricvid.py, using the real lyric text where a line matches. Usage: w2lines.py <whisper.json> <lyrics.txt> <out.json>
import json, sys, difflib
clean = lambda x: x.replace("♪", "").replace("\ufffd", "")  # whisper marks sung lines with ♪ (sometimes split into broken bytes)
w, lyr, out = sys.argv[1:4]
lyric_lines = [l.strip() for l in open(lyr) if l.strip() and not l.startswith("[")]
lines = []
for s in json.load(open(w))["transcription"]:
    text = clean(s["text"]).strip()
    if "[" in text or not any(c.isalnum() for c in text): continue
    words = []
    for t in s["tokens"]:
        if t["text"].startswith("[_"): continue
        tt = clean(t["text"])
        if tt.startswith(" ") or not words: words.append([t["offsets"]["from"], tt.strip()])
        else: words[-1][1] += tt
    words = [x for x in words if x[1]]
    best = difflib.get_close_matches(text, lyric_lines, 1, 0.6)
    if best and len(best[0].split()) == len(words):  # same word count: swap in the correct spelling
        words = [[a, b] for (a, _), b in zip(words, best[0].split())]
    lines.append({"start": s["offsets"]["from"], "end": s["offsets"]["to"],
                  "words": [{"start": a, "text": b} for a, b in words]})
assert lines and all(l["words"] for l in lines)
json.dump({"lyrics_sections": [{"lines": lines}]}, open(out, "w"))
print(len(lines), "lines;", " / ".join(" ".join(x["text"] for x in l["words"]) for l in lines[:6]))
