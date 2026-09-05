"""Audio sources for the dataset pipeline.

Primary source is **quranicaudio.com** (single host, predictable URLs,
high quality, complete mushafs)::

    https://download.quranicaudio.com/quran/{slug}/{surah:03d}.mp3

The per-reciter slug (which may include a subfolder like ``year1440``) is
scraped once from the reciter page and cached as a URL template.

Fallback source is **surahquran.com** (used for reciters missing from
quranicaudio, e.g. Al-Ossi), whose pages hotlink mp3quran.net / archive.org.
Legacy ``islamic-cdn`` support is kept for the three original reciters.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

import requests

logger = logging.getLogger(__name__)

BROWSER_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

_QA_DL_RE = re.compile(r"https://download\.quranicaudio\.com/[^\s\"'<>]+\.mp3")
_SQ_SOURCE_TAG_RE = re.compile(
    r"<source[^>]*?\ssrc\s*=\s*[\"']?([^\"'\s<>]+\.mp3[^\"'\s<>]*)", re.IGNORECASE
)
_SQ_MP3QURAN_RE = re.compile(r"https://server\d+\.mp3quran\.net/[^\s\"'<>]+\.mp3")
_SQ_ANY_MP3_RE = re.compile(r"https?://[^\s\"'<>]+\.mp3(?:\?[^\s\"'<>]*)?")
_NUM_TAIL_RE = re.compile(r"^(.*/)\d+(\.mp3(?:\?.*)?)$")


@dataclass(frozen=True)
class ReciterSpec:
    key: str
    display: str
    qa_id: int | None = None       # quranicaudio.com/quran/{id}
    sq_slug: str | None = None     # surahquran.com/mp3/{slug} fallback
    cdn_code: str | None = None    # islamic.network legacy code


RECITERS: dict[str, ReciterSpec] = {
    # --- Egyptian mujawwad legends ---
    "abdulbaset": ReciterSpec("abdulbaset", "Abdulbaset Abdussamad", 37, "Abdulbaset"),
    "minshawi": ReciterSpec("minshawi", "Mohamed Al-Minshawi", 6, "Al-Minshawi", "ar.minshawi"),
    "husary": ReciterSpec("husary", "Mahmoud Al-Hussary", 122, "Al-Hussary", "ar.husary"),
    "mustafa": ReciterSpec("mustafa", "Mustafa Ismail", 88),
    "banna": ReciterSpec("banna", "Mahmoud Ali Al-Banna", 129),
    # --- Haramain imams ---
    "sudais": ReciterSpec("sudais", "Abdurrahman As-Sudais", 7, "Alsudaes"),
    "shuraim": ReciterSpec("shuraim", "Saud Al-Shuraim", 4, "Al-Shuraim"),
    "maher": ReciterSpec("maher", "Maher Al-Muaiqly", 159, "maher"),
    "juhany": ReciterSpec("juhany", "Abdullah Al-Juhany", 1, "Al-Johany"),
    "dosari": ReciterSpec("dosari", "Yasser Al-Dosari", 97, "Al-Dosari"),
    # --- Contemporary murattal favourites ---
    "alafasy": ReciterSpec("alafasy", "Mishary Alafasy", 5, "Alafasi", "ar.alafasy"),
    "ghamdi": ReciterSpec("ghamdi", "Saad Al-Ghamdi", 13, "Al-Ghamdi"),
    "ajmy": ReciterSpec("ajmy", "Ahmed Al-Ajmy", 19, "Al-Ajmy"),
    "qatami": ReciterSpec("qatami", "Nasser Al-Qatami", 104, "qattamy"),
    "hani": ReciterSpec("hani", "Hani Ar-Rifai", 27, "Hani"),
    "abkar": ReciterSpec("abkar", "Idris Abkar", None, "Idris-Abkar"),
    # --- New wave ---
    "fares": ReciterSpec("fares", "Fares Abbad", 14, "Fares"),
    "kurdi": ReciterSpec("kurdi", "Raad Al-Kurdi", 168, "kordy"),
    "tunaiji": ReciterSpec("tunaiji", "Khalifa Al-Tunaiji", 161, "khalifa"),
    "ossi": ReciterSpec("ossi", "Abdul Rahman Al-Ossi", None, "AbdAlrahman-Al3osy"),
}

# Medium-length surahs: plenty of audio per file, bounded download size.
# (~80 min audio / ~900 clips per reciter; embedding means use a capped subset.)
TRAIN_SURAHS = [36, 55, 56, 67]
# Fresh short surahs (never used for training) for honest, lightweight evaluation.
EVAL_SURAHS = [78, 87, 93, 112]

_qa_template_cache: dict[int, str] = {}
_sq_template_cache: dict[str, str] = {}


def _templatize(mp3_url: str) -> str:
    m = _NUM_TAIL_RE.match(mp3_url)
    if not m:
        raise ValueError(f"Cannot templatize MP3 URL: {mp3_url}")
    head, tail = m.group(1), m.group(2)
    width = len(mp3_url) - len(head) - len(tail)
    return head + "{surah:0" + str(width) + "d}" + tail


def _get(url: str, timeout: int) -> requests.Response:
    resp = requests.get(url, headers={"User-Agent": BROWSER_UA}, timeout=timeout)
    resp.raise_for_status()
    return resp


# ---------------- quranicaudio ----------------

def resolve_qa_template(qa_id: int, timeout: int = 20) -> str:
    """Scrape the reciter page for its download URL pattern (cached)."""
    if qa_id in _qa_template_cache:
        return _qa_template_cache[qa_id]
    page = _get(f"https://quranicaudio.com/quran/{qa_id}", timeout)
    match = _QA_DL_RE.search(page.text)
    if not match:
        raise ValueError(f"No download link on https://quranicaudio.com/quran/{qa_id}")
    template = _templatize(match.group(0))
    assert template.format(surah=1) == match.group(0), template
    _qa_template_cache[qa_id] = template
    logger.info("quranicaudio %s -> %s", qa_id, template)
    return template


def qa_url(reciter_key: str, surah: int) -> str:
    spec = RECITERS[reciter_key]
    assert spec.qa_id is not None, f"{reciter_key} has no quranicaudio id"
    return resolve_qa_template(spec.qa_id).format(surah=surah)


def download_qa(reciter_key: str, surah: int, timeout: int = 120) -> bytes:
    resp = _get(qa_url(reciter_key, surah), timeout)
    return resp.content


def qa_exists(reciter_key: str, surah: int, timeout: int = 10) -> bool:
    try:
        resp = requests.head(
            qa_url(reciter_key, surah),
            headers={"User-Agent": BROWSER_UA},
            timeout=timeout,
            allow_redirects=True,
        )
        return resp.status_code == 200
    except requests.RequestException:
        return False


# ---------------- surahquran (fallback) ----------------

def _fetch_sq_surah_page_mp3(slug: str, timeout: int = 20) -> str:
    url = f"https://surahquran.com/mp3/{slug}/1.html"
    text = _get(url, timeout).text
    tag = _SQ_SOURCE_TAG_RE.search(text)
    if tag:
        return tag.group(1)
    quran = _SQ_MP3QURAN_RE.search(text)
    if quran:
        return quran.group(0)
    for any_mp3 in _SQ_ANY_MP3_RE.findall(text):
        if "surahquran.com" not in any_mp3:
            return any_mp3
    raise ValueError(f"No MP3 link found on {url}")


def resolve_sq_template(slug: str) -> str:
    if slug in _sq_template_cache:
        return _sq_template_cache[slug]
    mp3_url = _fetch_sq_surah_page_mp3(slug)
    template = _templatize(mp3_url)
    assert template.format(surah=1) == mp3_url, template
    _sq_template_cache[slug] = template
    logger.info("surahquran %s -> %s", slug, template)
    return template


def surahquran_url(reciter_key: str, surah: int) -> str:
    spec = RECITERS[reciter_key]
    if spec.sq_slug is None:
        raise ValueError(f"Reciter {reciter_key} has no surahquran slug")
    return resolve_sq_template(spec.sq_slug).format(surah=surah)


def surahquran_exists(reciter_key: str, surah: int, timeout: int = 10) -> bool:
    try:
        resp = requests.head(
            surahquran_url(reciter_key, surah),
            headers={"User-Agent": BROWSER_UA},
            timeout=timeout,
            allow_redirects=True,
        )
        return resp.status_code == 200
    except requests.RequestException:
        return False


def download_surahquran(reciter_key: str, surah: int, timeout: int = 60) -> bytes:
    return _get(surahquran_url(reciter_key, surah), timeout).content


# ---------------- unified helpers ----------------

def reciter_origin(reciter_key: str) -> str:
    """Where to fetch a reciter from: quranicaudio preferred, else surahquran."""
    spec = RECITERS[reciter_key]
    if spec.qa_id is not None:
        return "quranicaudio"
    if spec.sq_slug is not None:
        return "surahquran"
    raise ValueError(f"Reciter {reciter_key} has no download source")


def download_reciter_surah(reciter_key: str, surah: int) -> bytes:
    if reciter_origin(reciter_key) == "quranicaudio":
        return download_qa(reciter_key, surah)
    return download_surahquran(reciter_key, surah)
