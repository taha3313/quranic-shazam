"""Inspect pages with missing slugs for download URL patterns."""

import re
import sys

sys.path.insert(0, ".")

import requests

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Chrome/120.0"}

for qid in [159, 13, 168]:
    page = requests.get(f"https://quranicaudio.com/quran/{qid}", headers=UA, timeout=20)
    text = page.text
    print(f"=== quran/{qid} bytes={len(text)}")
    for pat in [
        r"https?://download[^\s\"'<>]*",
        r"href=\"([^\"]*001[^\"]*)\"",
        r"mishaari|maher|ghamdi|kurdi|muaiqly|raad",
    ]:
        hits = sorted(set(re.findall(pat, text, re.IGNORECASE)))[:6]
        print(f"  {pat}: {hits}")
