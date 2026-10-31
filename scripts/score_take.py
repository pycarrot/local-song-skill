# Score how much of the lyric a take actually sings, from its check_lyrics.sh transcript. Higher = clearer, more complete.
# Usage: score_take.py <take.whisper.json> <lyrics.txt> [more.whisper.json …]   (one row per take, best first)
import json, sys, re, difflib, unicodedata
from w2lines import matching_blocks  # global alignment: a clean later chorus can't swallow the sections before it
# letters/marks/digits only, no spaces: works the same for English, Thai, Japanese…
letters = lambda s: "".join(c for c in s.lower() if unicodedata.category(c)[0] in "LMN")
norm = lambda s: letters(re.sub(r"\(.*?\)", "", s))  # (backing vocals) and Whisper's "(music)" notes are not scored
lyrics = [l.strip() for l in open(sys.argv[2]) if l.strip() and not l.lstrip().startswith("[")]

def score(path):
    segs = json.load(open(path, errors="replace"))["transcription"]
    heard = norm(" ".join(s["text"] for s in segs if "[" not in s["text"]))
    def found(line):  # best fuzzy match of this line anywhere in the transcript
        n = len(line)
        return max((difflib.SequenceMatcher(None, line, heard[i:i + n]).ratio() for i in range(0, max(1, len(heard) - n + 1), 2)), default=0)
    per = [(found(norm(l)), l) for l in lyrics if norm(l)]
    # penalises missing/extra sections; backing vocals stay in, since Whisper often hears a shouted "(Hey!)"
    ref = letters(" ".join(lyrics))
    order = 2 * sum(n for _, _, n in matching_blocks(ref, heard)) / max(len(ref) + len(heard), 1)
    return sum(s >= 0.6 for s, _ in per) / len(per), order, per  # a line is heard when >= 60% of it matches

rows = sorted(((*score(p), p) for p in [sys.argv[1]] + sys.argv[3:]), key=lambda r: -(r[0] + r[1]))
for lines, order, per, p in rows:
    print(f"{p}: lines {lines:.0%}  in-order {order:.0%}  weak {sum(s < 0.6 for s, _ in per)}"
          + "".join(f"\n    {s:4.0%} {l}" for s, l in sorted(set(per))[:5]))  # the five weakest, even when none is under 60%
