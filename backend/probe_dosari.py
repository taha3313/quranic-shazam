"""Inspect Al-Dosari surah page for audio URL patterns."""

import re
import sys

sys.path.insert(0, ".")

import requests

from scripts.sources import BROWSER_UA

resp = requests.get(
    "https://surahquran.com/mp3/Al-Dosari/1.html",
    headers={"User-Agent": BROWSER_UA},
    timeout=30,
)
print("status:", resp.status_code, "bytes:", len(resp.text))
for pat in [
    r"https?://[^\s\"'<>]*mp3[^\s\"'<>]*",
    r"https?://[^\s\"'<>]*(?:audio|server|cdn)[^\s\"'<>]*",
    r"<audio[^>]*>",
    r"<source[^>]*>",
]:
    hits = sorted(set(re.findall(pat, resp.text)))
    print(f"--- {pat}: {len(hits)}")
    for h in hits[:8]:
        print("   ", h[:160])
