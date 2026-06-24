from __future__ import annotations

import json
import re
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import urlparse

from .fetch import download_file

MEDIA_KINDS = ("images", "audio", "video")


@dataclass(frozen=True)
class MediaItem:
    kind: str
    index: int
    url: str
    path: str
    strategy: str
    timeout: int
    probe: bool = False


@dataclass
class MediaResult:
    kind: str
    url: str
    path: str | None = None
    bytes: int = 0
    ok: bool = False
    skipped_existing: bool = False
    strategy: str | None = None
    error: str | None = None
    probe: dict | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def _uniq(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            out.append(value)
    return out


def collect_media_urls(post: dict, publication_host: str) -> dict[str, list[str]]:
    body = post.get("body_html") or ""
    urls = {u.replace("&amp;", "&") for u in re.findall(r"https?://[^\"'<>\s)]+", body)}
    image_urls: list[str] = []
    for key in ["cover_image", "podcast_episode_image_url", "podcast_art_url"]:
        if post.get(key):
            image_urls.append(post[key])
    for url in urls:
        lu = url.lower()
        if "/image/fetch" in lu or re.search(r"\.(png|jpe?g|webp|gif)(\?|$)", lu):
            image_urls.append(url)

    audio_urls: list[str] = []
    if post.get("podcast_url"):
        audio_urls.append(post["podcast_url"])
    inbox = post.get("inboxItem") or {}
    if inbox.get("audio_url"):
        audio_urls.append(inbox["audio_url"])

    video_urls: list[str] = []
    video = post.get("videoUpload") or {}
    if video.get("id") and publication_host:
        video_urls.append(f"https://{publication_host}/api/v1/video/upload/{video['id']}/src")
    if video.get("mux_playback_id"):
        video_urls.append(f"https://stream.mux.com/{video['mux_playback_id']}.m3u8")

    return {"images": _uniq(image_urls), "audio": _uniq(audio_urls), "video": _uniq(video_urls)}


def write_url_lists(media_dir: Path, urls: dict[str, list[str]]) -> None:
    media_dir.mkdir(parents=True, exist_ok=True)
    for kind, filename in [("images", "image_urls.txt"), ("audio", "audio_urls.txt"), ("video", "video_urls.txt")]:
        values = urls.get(kind, [])
        (media_dir / filename).write_text("\n".join(values) + ("\n" if values else ""), encoding="utf-8")


def infer_image_extension(url: str) -> str:
    clean = urlparse(url).path.lower()
    ext = clean.rsplit(".", 1)[-1] if "." in clean else "jpg"
    if ext not in {"jpg", "jpeg", "png", "webp", "gif"}:
        return "jpg"
    return ext


def build_media_plan(urls: dict[str, list[str]]) -> list[MediaItem]:
    plan: list[MediaItem] = []
    for i, url in enumerate(urls.get("images", []), start=1):
        ext = infer_image_extension(url)
        plan.append(MediaItem("images", i, url, f"media/images/image_{i:02d}.{ext}", "direct-image", 300))
    for i, url in enumerate(urls.get("audio", []), start=1):
        plan.append(MediaItem("audio", i, url, f"media/audio/audio_{i:02d}.mp3", "substack-audio", 600))
    for i, url in enumerate(urls.get("video", []), start=1):
        if ".m3u8" in urlparse(url).path.lower():
            # Recorded as candidate for future ffmpeg/HLS support; try only after direct Substack source fails.
            strategy = "mux-hls-candidate"
        else:
            strategy = "substack-video-src"
        plan.append(MediaItem("video", i, url, f"media/video/video_{i:02d}.mp4", strategy, 1200, probe=True))
    return plan


def download_media_item(out_dir: Path, cookies: Path, item: MediaItem, force: bool = False) -> MediaResult:
    dest = out_dir / item.path
    result = MediaResult(kind=item.kind, url=item.url, path=item.path, strategy=item.strategy)
    if item.strategy == "mux-hls-candidate":
        result.error = "HLS/Mux fallback is recorded but not downloaded in MS3 direct strategy"
        return result
    try:
        size, downloaded_now = download_file(item.url, dest, cookies, timeout=item.timeout, force=force)
        result.bytes = size
        result.ok = True
        result.skipped_existing = not downloaded_now
        if item.probe and dest.exists() and dest.stat().st_size > 0:
            try:
                result.probe = ffprobe(dest)
            except Exception as e:
                result.error = f"download ok; ffprobe failed: {e}"
        return result
    except Exception as e:
        result.error = str(e)
        return result


def download_media(out_dir: Path, cookies: Path, urls: dict[str, list[str]], force: bool = False) -> dict[str, list[dict]]:
    media_dir = out_dir / "media"
    write_url_lists(media_dir, urls)
    plan = build_media_plan(urls)
    (media_dir / "download_plan.json").write_text(json.dumps([asdict(item) for item in plan], indent=2), encoding="utf-8")
    results: dict[str, list[dict]] = {"images": [], "audio": [], "video": []}

    direct_video_done = False
    for item in plan:
        if item.kind == "video" and direct_video_done:
            # One full video artifact is enough; leave additional candidates in download_plan.json/video_urls.txt.
            continue
        res = download_media_item(out_dir, cookies, item, force=force)
        results[item.kind].append(res.to_dict())
        if item.kind == "video" and res.ok:
            direct_video_done = True
    (media_dir / "download_results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    return results


def ffprobe(path: Path) -> dict:
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration,size:stream=codec_type,codec_name,width,height", "-of", "json", str(path)]
    proc = subprocess.run(cmd, check=True, text=True, capture_output=True)
    result = json.loads(proc.stdout)
    (path.parent / f"{path.stem}.ffprobe.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result
