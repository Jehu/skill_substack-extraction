from __future__ import annotations

import http.cookiejar
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/125 Safari/537.36"


def load_cookiejar(cookies_file: Path) -> http.cookiejar.CookieJar:
    jar = http.cookiejar.MozillaCookieJar(str(cookies_file))
    jar.load(ignore_discard=True, ignore_expires=True)
    return jar


def opener_for(cookies_file: Path | None = None) -> urllib.request.OpenerDirector:
    if cookies_file:
        jar = load_cookiejar(cookies_file)
        return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    return urllib.request.build_opener()


def fetch_url(url: str, cookies_file: Path | None = None, timeout: int = 60) -> tuple[bytes, dict[str, str], str]:
    opener = opener_for(cookies_file)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with opener.open(req, timeout=timeout) as resp:
            body = resp.read()
            headers = {k.lower(): v for k, v in resp.headers.items()}
            final_url = resp.geturl()
            return body, headers, final_url
    except urllib.error.HTTPError as e:
        body = e.read()
        raise RuntimeError(f"HTTP {e.code} for {url}: {body[:200]!r}") from e


def download_file(
    url: str,
    dest: Path,
    cookies_file: Path | None = None,
    timeout: int = 300,
    force: bool = False,
    min_bytes: int = 1,
) -> tuple[int, bool]:
    """Download URL to dest. Returns (bytes, downloaded_now).

    Existing files >= min_bytes are treated as completed unless force=True. This makes
    media stages safely resumable without relying on remote range support.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size >= min_bytes and not force:
        return dest.stat().st_size, False
    tmp = dest.with_suffix(dest.suffix + ".part")
    if tmp.exists():
        tmp.unlink()
    body, _headers, _final = fetch_url(url, cookies_file=cookies_file, timeout=timeout)
    tmp.write_bytes(body)
    if tmp.stat().st_size < min_bytes:
        raise RuntimeError(f"downloaded file too small for {url}: {tmp.stat().st_size} bytes")
    tmp.replace(dest)
    return dest.stat().st_size, True


def host_for(url: str) -> str:
    return urlparse(url).netloc
