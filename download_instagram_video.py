#!/usr/bin/env python3

"""Instagram video downloader (yt-dlp first, GraphQL fallback).

Features:
- Uses yt-dlp to download and merge video+audio (format: "bv*+ba/b").
- Detects FFmpeg on PATH, from imageio-ffmpeg, or via environment/configured path.
- Falls back to GraphQL extraction only when yt-dlp fails to extract the post.
- Clear logging and error classification for common failure modes.

Compatible: Windows, Linux, Railway (Nixpacks), Python 3.11+
"""

from typing import Optional, Dict

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

try:
    import yt_dlp
except Exception:  # pragma: no cover - allow module to run without yt-dlp for fallback
    yt_dlp = None

try:
    import imageio_ffmpeg
except Exception:
    imageio_ffmpeg = None

# Default ffmpeg directory (can be overridden via env FFMPEG_PATH)
DEFAULT_FFMPEG_LOC = os.environ.get("FFMPEG_PATH", "")


def extract_shortcode(url: str) -> str:
    """Extract Instagram shortcode from a post or reel URL."""
    match = re.search(r"/(p|reel|reels)/([a-zA-Z0-9_-]+)", url)
    if not match or not match.group(2):
        raise ValueError("Invalid Instagram URL. Expected a post or reel URL.")
    shortcode = match.group(2)
    if shortcode.lower() == "shortcode":
        raise ValueError("Replace placeholder SHORTCODE with a real shortcode or URL.")
    return shortcode


def build_graphql_payload(shortcode: str) -> bytes:
    """Build the POST body for the GraphQL fallback payload."""
    return urlencode(
        {
            "av": "0",
            "__d": "www",
            "__user": "0",
            "__a": "1",
            "variables": json.dumps({"shortcode": shortcode}),
        },
        doseq=True,
    ).encode("utf-8")


def find_ffmpeg_binary(configured_path: Optional[str] = None) -> Optional[str]:
    """Detect an ffmpeg executable.

    Checks PATH, configured_path, DEFAULT_FFMPEG_LOC, and imageio_ffmpeg.
    Returns the path to the executable or None.
    Prints which candidate was chosen.
    """
    candidates = []

    # 1) explicit configured path (env or passed)
    if configured_path:
        candidates.append(configured_path)

    # 2) environment override
    env_path = os.environ.get("FFMPEG_PATH")
    if env_path:
        candidates.append(env_path)

    # 3) default variable (from earlier code)
    if DEFAULT_FFMPEG_LOC:
        candidates.append(DEFAULT_FFMPEG_LOC)

    # 4) PATH lookups
    which = shutil.which("ffmpeg") or shutil.which("ffmpeg.exe")
    if which:
        candidates.insert(0, which)

    # 5) imageio-ffmpeg
    if imageio_ffmpeg is not None:
        try:
            exe = imageio_ffmpeg.get_ffmpeg_exe()
            if exe:
                candidates.append(exe)
        except Exception:
            pass

    # Normalize and find first usable executable
    for cand in candidates:
        if not cand:
            continue
        p = Path(cand)

        # If candidate is a directory, look for ffmpeg/ffmpeg.exe inside
        if p.is_dir():
            exe = p / ("ffmpeg.exe" if os.name == "nt" else "ffmpeg")
            if exe.exists() and exe.is_file():
                if _validate_ffmpeg_executable(exe):
                    print(f"Using ffmpeg: {exe}")
                    return str(exe)
                continue

        # If candidate is a file path, validate it
        if p.is_file():
            if _validate_ffmpeg_executable(p):
                print(f"Using ffmpeg: {p}")
                return str(p)
            continue

        # If candidate is a name or PATH entry, resolve it
        which_path = shutil.which(str(p))
        if which_path:
            exe = Path(which_path)
            if _validate_ffmpeg_executable(exe):
                print(f"Using ffmpeg: {exe}")
                return str(exe)

    print("FFmpeg executable not found on PATH or configured locations.")
    return None


def classify_error(exc: Exception) -> str:
    """Map common errors to user-friendly categories."""
    msg = str(exc).lower()
    if "private" in msg or "this account is private" in msg:
        return "private_account"
    if "login" in msg or "401" in msg or "unauthorized" in msg:
        return "login_required"
    if "geo" in msg or "not available in your country" in msg:
        return "geo_restricted"
    if "not found" in msg or "404" in msg or "deleted" in msg:
        return "deleted_or_unavailable"
    if "unsupported url" in msg or "invalid" in msg:
        return "invalid_url"
    if "timed out" in msg or "timeout" in msg or "network" in msg:
        return "network_error"
    if "ffmpeg" in msg and ("not found" in msg or "could not find" in msg):
        return "ffmpeg_missing"
    return "unknown_error"


def _validate_ffmpeg_executable(candidate: Path) -> bool:
    """Verify that the candidate is a working ffmpeg executable."""
    try:
        result = subprocess.run(
            [str(candidate), "-version"], capture_output=True, text=True, timeout=10
        )
        return result.returncode == 0 and "ffmpeg version" in result.stdout.lower()
    except Exception:
        return False


def download_with_ytdlp(url: str, output_path: Path, ffmpeg_path: Optional[str]) -> Path:
    """Download using yt-dlp, merging video+audio into MP4.

    Uses format selection: "bv*+ba/b" and merge_output_format="mp4".
    Raises detailed exceptions on failure.
    """
    if yt_dlp is None:
        raise RuntimeError("yt-dlp is not installed")

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Configure yt-dlp options
    ydl_opts: Dict = {
        "format": "bv*+ba/b",
        "merge_output_format": "mp4",
        "outtmpl": str(output_path),
        "noplaylist": True,
        "quiet": False,
        "no_warnings": True,
    }

    if ffmpeg_path:
        # Use the ffmpeg executable path when possible; yt-dlp accepts either
        # the binary file or the directory containing the binary.
        ffmpeg_path = str(Path(ffmpeg_path).resolve())
        ydl_opts["ffmpeg_location"] = ffmpeg_path
        ydl_opts["prefer_ffmpeg"] = True
        print(f"yt-dlp ffmpeg_location: {ffmpeg_path}")

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Extract info first to present choices and detect separate streams
            info = ydl.extract_info(url, download=False)

            # Logging selected or available formats
            if isinstance(info, dict):
                if info.get("requested_formats"):
                    vfmt = info["requested_formats"][0]
                    afmt = info["requested_formats"][1] if len(info["requested_formats"]) > 1 else None
                    print("Selected video format:", vfmt.get("format_id"), vfmt.get("ext"), vfmt.get("format"))
                    if afmt:
                        print("Selected audio format:", afmt.get("format_id"), afmt.get("ext"), afmt.get("format"))
                else:
                    print("Selected format:", info.get("format"))

            print("Starting download with yt-dlp...")
            # This will perform download and merging using configured ffmpeg
            ydl.download([url])

            print(f"Download complete: {output_path}")
            return output_path

    except Exception as exc:  # noqa: BLE001 - map yt-dlp exceptions
        kind = classify_error(exc)
        raise RuntimeError(f"yt-dlp download failed ({kind}): {exc}") from exc


def fetch_instagram_media(url: str) -> str:
    """Fallback GraphQL extraction for video URL. Kept for legacy fallback only.

    Returns a direct video URL (may be DASH/video-only). Prefer yt-dlp instead.
    """
    shortcode = extract_shortcode(url)

    request_url = "https://www.instagram.com/graphql/query"

    headers = {
        "User-Agent": "Mozilla/5.0",
        "Content-Type": "application/x-www-form-urlencoded",
        "Referer": f"https://www.instagram.com/p/{shortcode}/",
    }

    req = Request(request_url, data=build_graphql_payload(shortcode), headers=headers, method="POST")

    try:
        with urlopen(req, timeout=25) as response:
            body = response.read().decode("utf-8")
    except HTTPError as exc:
        raise RuntimeError(f"Instagram request failed with status {exc.code}") from exc
    except URLError as exc:
        raise RuntimeError(f"Network error: {exc}") from exc

    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Unexpected response from Instagram") from exc

    data = payload.get("data")
    if not isinstance(data, dict):
        raise RuntimeError("Post not found or not accessible (GraphQL)")

    media = data.get("xdt_shortcode_media") or data.get("shortcode_media")
    if not isinstance(media, dict) or not media.get("is_video"):
        raise RuntimeError("The URL does not point to a video (GraphQL)")

    video_url = media.get("video_url")
    if not video_url:
        raise RuntimeError("Video URL not found in Instagram GraphQL response")

    return video_url


def download_instagram(url: str, output_path: str = "downloaded_video.mp4") -> Path:
    """Top-level helper: try yt-dlp first, falling back to GraphQL when necessary."""
    outp = Path(output_path)

    ffmpeg_exec = find_ffmpeg_binary()
    if ffmpeg_exec is None:
        print("Warning: FFmpeg not found. yt-dlp may not be able to merge separate streams.")

    # Prefer yt-dlp
    if yt_dlp is not None:
        try:
            result = download_with_ytdlp(url, outp, ffmpeg_exec)
            print(f"Final output: {result}")
            return result
        except Exception as exc:
            print(f"yt-dlp failed: {exc}")
            print("Falling back to GraphQL extraction...")

    # Fallback: use GraphQL direct download (may be video-only)
    video_url = fetch_instagram_media(url)
    # Download with urllib as a last resort (video-only possibility)
    print("Downloading direct video URL (GraphQL fallback). This may be video-only if audio is separate.")
    outp.parent.mkdir(parents=True, exist_ok=True)
    req = Request(video_url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urlopen(req, timeout=60) as response, outp.open("wb") as fh:
            shutil.copyfileobj(response, fh)
    except Exception as exc:
        kind = classify_error(exc)
        raise RuntimeError(f"Fallback download failed ({kind}): {exc}") from exc

    print(f"Saved fallback output to: {outp}")
    return outp


