"""Resolve quranicaudio download slugs for reciter ids and check surah availability."""

import re
import sys

sys.path.insert(0, ".")

import requests

SLUG_RE = re.compile(r"download\.quranicaudio\.com/quran/([^/\"']+)/001\.mp3")
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Chrome/120.0"}

IDS = {
    "abdulbaset": 37,
    "minshawi": 6,
    "husary": 122,
    "mustafa": 88,
    "banna": 129,
    "sudais": 7,
    "shuraim": 4,
    "maher": 159,
    "juhany": 1,
    "dosari": 97,
    "alafasy": 5,
    "ghamdi": 13,
    "ajmy": 19,
    "qatami": 104,
    "hani": 27,
    "abkar": 116,
    "fares": 14,
    "kurdi": 168,
    "tunaiji": 161,
}

TRAIN = [12, 18, 19, 21, 36, 55, 56, 67]
EVAL = [7, 23, 32, 50]


def check(slug, surahs):
    ok = []
    with requests.Session() as sess:
        sess.headers.update(UA)
        for s in surahs:
            try:
                r = sess.head(
                    f"https://download.quranicaudio.com/quran/{slug}/{s:03d}.mp3",
                    timeout=10,
                    allow_redirects=True,
                )
                if r.status_code == 200:
                    ok.append(s)
            except requests.RequestException:
                pass
    return ok


print("SLUGS:")
slugs = {}
for key, qid in IDS.items():
    try:
        page = requests.get(f"https://quranicaudio.com/quran/{qid}", headers=UA, timeout=20)
        m = SLUG_RE.search(page.text)
        slug = m.group(1) if m else None
        slugs[key] = slug
        print(f"  {key} ({qid}): {slug}")
    except Exception as exc:  # noqa: BLE001
        print(f"  {key} ({qid}): ERROR {exc}")

print("AVAILABILITY:")
for key, slug in slugs.items():
    if not slug:
        print(f"  {key}: NO SLUG")
        continue
    print(f"  {key}: train={check(slug, TRAIN)} eval={check(slug, EVAL)}")
