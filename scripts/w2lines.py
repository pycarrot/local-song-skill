# Align lyrics.txt to a whisper transcript (check_lyrics.sh output) -> lines.json for lyricvid.py.
# The screen always shows the real lyric lines and words; whisper only supplies the times. Matching is done
# character by character over the whole song (longest common subsequence), so merged/split segments, misheard words and "(music)" notes don't matter.
# Usage: w2lines.py <audio>.whisper.json lyrics.txt lines.json      (self-test: w2lines.py --test)
import json, sys, unicodedata
MS_PER_CHAR = 70  # pace for placing unheard words next to a heard one (~250 ms per English word)

def norm(s):  # letters, marks (Thai vowels/tones) and digits only, lower case
    return [c for c in s.lower() if unicodedata.category(c)[0] in "LMN"]

def heard(transcript):
    """Each spoken character with its (start, end) ms; DTW time (t_dtw, centiseconds) when present."""
    toks = [t for s in transcript for t in s["tokens"] if not t["text"].startswith("[_")]
    dtw = [t.get("t_dtw", -1) for t in toks]
    last = max(dtw, default=-1)
    stuck = dtw.count(last) > 2  # whisper.cpp DTW piles every token of the final window onto one end-of-audio time
    out, depth = [], 0
    for t, d in zip(toks, dtw):
        text = t["text"]
        for c in text:  # drop "(upbeat music)" / "[Music]" notes
            depth += c in "([" ; depth -= c in ")]"; depth = max(depth, 0)
        if depth or ")" in text or "]" in text: continue
        t0 = d * 10 if d >= 0 and not (stuck and d == last) else t["offsets"]["from"]
        out += [(c, t0, max(t0, t["offsets"]["to"])) for c in norm(text)]
    return out

def matching_blocks(a, b):
    """(i, j, n) runs where lyric letters a[i:i+n] were heard as b[j:j+n]. A global alignment: every matched letter
    scores 2 and every new run costs 1, so whole runs beat letters scattered by chance, and unlike difflib's greedy
    longest-block-first search a clear chorus 2 can't pull chorus 1 of the lyrics onto itself. It runs on the
    reversed strings so the traceback walks from the song's start: a repeat goes to its first occurrence."""
    ra, rb, NO = a[::-1], b[::-1], -1 << 40
    pm, pb, back = [NO] * (len(rb) + 1), [0] * (len(rb) + 1), []  # best score ending in a match / overall
    for x in ra:
        cm, cb, bt = [NO], [0], bytearray(len(rb) + 1)  # bt bits: 1 best is a match, 2 match extends a run, 4 skip lyric letter
        for j, y in enumerate(rb, 1):
            f, mv = 0, NO
            if x == y:
                mv = max(pm[j - 1] + 2, pb[j - 1] + 1)
                f |= 2 * (pm[j - 1] + 2 == mv)
            sv = max(pb[j], cb[-1])
            f |= 4 * (pb[j] == sv)
            f |= mv >= sv
            cm.append(mv); cb.append(max(mv, sv)); bt[j] = f
        back.append(bt); pm, pb = cm, cb
    i, j, in_match, blocks = len(a), len(b), False, []
    while i and j:
        f = back[i - 1][j]
        if in_match or f & 1:
            oi, oj = len(a) - i, len(b) - j  # back to forward indices, visited in song order
            if blocks and blocks[-1][0] + blocks[-1][2] == oi and blocks[-1][1] + blocks[-1][2] == oj: blocks[-1][2] += 1
            else: blocks.append([oi, oj, 1])
            in_match = bool(f & 2); i -= 1; j -= 1
        else:
            if f & 4: i -= 1
            else: j -= 1
    return blocks

def align(lyric_lines, transcript):
    words = [(i, w) for i, l in enumerate(lyric_lines) for w in l.split()]
    chars = [(k, c) for k, (_, w) in enumerate(words) for c in norm(w)]
    pos = [0]  # lyric character offset of each word, so unheard words take time in proportion to their length
    for _, w in words: pos.append(pos[-1] + len(norm(w)))
    got = heard(transcript)
    start, end, skip = [None] * len(words), [None] * len(words), [0] * len(words)  # skip: letters before the first heard one
    for a, b, n in matching_blocks([c for _, c in chars], [c for c, _, _ in got]):
        ks = [chars[a + j][0] for j in range(n)]
        chance = (sum(unicodedata.category(chars[a + j][1])[0] != "M" for j in range(n)) < 3  # 1-2 letters in a gap are chance
                  or n < 5 and not any(ks.count(k) == pos[k + 1] - pos[k] for k in set(ks)))  # so are 3-4 letters inside a longer word
        for j in range(n):
            k, (_, t0, t1) = ks[j], got[b + j]
            if chance:  # ...but they still stretch the end of a word already placed (a Thai line is one word)
                if start[k] is not None and t0 - end[k] < 1000: end[k] = t1  # not across a pause (hallucinated outro)
                continue
            if start[k] is None:
                lead = 0  # unheard letters just before it in the same whisper token were sung at that token's time
                while b + j - lead > 0 and got[b + j - lead - 1][1] == t0: lead += 1
                start[k], skip[k] = t0, max(a + j - pos[k] - lead, 0)
            end[k] = t1
    known = [k for k in range(len(words)) if start[k] is not None]
    if not known: sys.exit("no lyric matched the transcript; nothing to time the video with")
    stop_all = max(t["offsets"]["to"] for s in transcript for t in s["tokens"])  # incl. "♪"/"(music)" over an unheard outro
    # this song's own singing pace, never faster than MS_PER_CHAR (a Thai ballad runs ~3x slower per letter than
    # English pop): the median over neighbouring heard words, so instrumental breaks don't inflate it
    rates = sorted((start[q] - start[p]) / (pos[q] - pos[p]) for p, q in zip(known, known[1:]))
    pace = max(MS_PER_CHAR, rates[(len(rates) - 1) // 2] if rates else 0)
    for p, k in zip([None] + known, known):  # only the end of a word was heard (Thai lines are one 'word'): start earlier
        if skip[k]: start[k] = min(start[k], max(start[k] - round(pace * skip[k]), 0 if p is None else end[p]))
    for k in range(len(words)):  # unheard words: interpolate between heard neighbours by lyric length
        if start[k] is not None: continue
        p = max((x for x in known if x < k), default=None); q = min((x for x in known if x > k), default=None)
        if p is None:  # before the first heard word: natural pace back from it, spread over [0, it] if that runs out
            start[k] = max(round(start[q] * pos[k] / max(pos[q], 1)), start[q] - round(pace * (pos[q] - pos[k])))
        elif q is None:  # after the last heard word: natural pace on from it, squeezed to end by the transcript's end
            start[k] = min(start[p] + round(pace * (pos[k] - pos[p])),
                           round(start[p] + (stop_all - start[p]) * (pos[k] - pos[p]) / max(pos[-1] - pos[p], 1)))
        else:
            start[k] = round(start[p] + (start[q] - start[p]) * (pos[k] - pos[p]) / max(pos[q] - pos[p], 1))
            if words[p][0] < words[k][0]:  # unheard lines after a break: sung at the song's pace up to the next heard word
                start[k] = max(start[k], start[q] - MS_PER_CHAR * (pos[q] - pos[k]))
            elif words[p][0] == words[k][0] < words[q][0]:  # closing words of a line before a break: go on from the heard word's end
                start[k] = min(start[k], end[p] + MS_PER_CHAR * (pos[k] - pos[p + 1]))
    lines = []
    for i, l in enumerate(lyric_lines):
        ks = [k for k, (li, _) in enumerate(words) if li == i]
        if not ks: continue
        stop = max([end[k] for k in ks if end[k] is not None] or [start[ks[-1]] + 600])
        lines.append({"start": start[ks[0]], "end": max(stop, start[ks[-1]]),
                      "words": [{"start": start[k], "text": words[k][1]} for k in ks]})
    return lines, len(known) / len(words)

def test():
    tok = lambda text, cs, dtw=None: {"text": text, "offsets": {"from": cs * 10, "to": cs * 10 + 300}, "t_dtw": cs if dtw is None else dtw}
    seg = lambda *t: {"tokens": list(t)}
    tr = [seg(tok(" (upbeat", 50), tok(" music)", 90)),  # note at 0.5 s must not become a lyric
          seg(tok(" the", 200), tok(" clock", 230), tok(" died", 260), tok(" we", 300), tok(" ran", 330))]  # two lines merged
    lines, cov = align(["The clock died", "We ran away"], tr)
    assert [w["text"] for w in lines[0]["words"]] == ["The", "clock", "died"] and lines[0]["start"] == 2000, lines
    assert lines[1]["start"] == 3000 and lines[1]["words"][2]["start"] > 3300 and cov == 5 / 6, lines  # "away" unheard
    # hallucinated outro with stuck DTW: the 3 letters "our" must not time "pour"; stuck tokens fall back to their offsets
    tr = [seg(tok(" let", 100), tok(" it", 130), tok(" rain", 160), tok(" so", 200), tok(" poor", 230)),
          seg(*[tok(w, 2000 + 30 * i, dtw=2500) for i, w in enumerate([" out", " of", " our", " day"])])]
    lines, _ = align(["Let it rain, slow pour"], tr)
    assert lines[0]["words"][-1]["start"] < 3000 and heard(tr)[-1][1] == 20900, lines
    # unheard first words after an instrumental break stay next to the heard rest of their line
    # ...and unheard last words before it follow straight on from the end of the heard word before them
    tr = [seg(tok(" we", 100), tok(" ran", 130)), seg(tok(" seen", 800), tok(" the", 830), tok(" students", 860))]
    lines, _ = align(["We ran away", "Dean of students"], tr)
    assert 7000 < lines[1]["start"] < lines[1]["words"][1]["start"] < 8600 and lines[0]["words"][2]["start"] == 1600, lines
    # a clear second chorus must not pull the first chorus line onto it (difflib's longest-block-first did)
    tr = [seg(tok(" hold", 100), tok(" me", 130), tok(" clothes", 160), tok(" to", 200), tok(" night", 230)),
          seg(tok(" walkin", 500), tok(" round", 530), tok(" a", 560), tok(" sweep", 590)),
          seg(tok(" hold", 900), tok(" me", 930), tok(" close", 960), tok(" tonight", 1000))]
    lines, _ = align(["Hold me close tonight", "Walking down the street", "Hold me close tonight"], tr)
    assert [l["start"] for l in lines] == [1000, 5000, 9000], lines
    # a repeated word goes to its first occurrence, not to a later one
    tr = [seg(tok(" wave", 100), tok(" bye", 130), tok(" bye", 160), tok(" bye", 400), tok(" bye", 430))]
    lines, _ = align(["Wave bye-bye"], tr)
    assert lines[0]["words"][1]["start"] == 1300, lines
    # only the end of a word heard: start a little earlier, but not for letters heard inside the same token ("mayo")
    tr = [seg(tok(" mayo", 200), tok(" hissing", 250))]
    lines, _ = align(["Radio hissing"], tr)
    assert 1800 <= lines[0]["start"] < 2000, lines
    print("ok")

if __name__ == "__main__":
    if sys.argv[1:] == ["--test"]: test(); sys.exit()
    w, lyr, out = sys.argv[1:4]
    lyric_lines = [l.strip() for l in open(lyr) if l.strip() and not l.lstrip().startswith("[")]
    lines, cov = align(lyric_lines, json.load(open(w, errors="replace"))["transcription"])
    json.dump({"lyrics_sections": [{"lines": lines}]}, open(out, "w"), ensure_ascii=False)
    print(f"{len(lines)} lines, {cov:.0%} of words heard (the rest are interpolated)")
    if cov < 0.5: print("warning: under half the words were heard, so the timing is rough")
