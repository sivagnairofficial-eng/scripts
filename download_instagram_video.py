#!/usr/bin/env python3

import json
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
except ImportError:  # pragma: no cover
    print("yt_dlp module not found. Falling back to manual download method.")
    yt_dlp = None

try:
    import imageio_ffmpeg
except ImportError:  # pragma: no cover
    imageio_ffmpeg = None


def extract_shortcode(url: str) -> str:
    match = re.search(r"/(p|reel|reels)/([a-zA-Z0-9_-]+)", url)
    if not match or not match.group(2):
        raise ValueError("Invalid Instagram URL. Expected a post or reel URL.")

    shortcode = match.group(2)
    if shortcode.lower() == "shortcode":
        raise ValueError(
            "Please replace the placeholder SHORTCODE with a real Instagram shortcode or URL."
        )

    return shortcode


def build_graphql_payload(shortcode: str) -> str:
    return urlencode(
        {
            "av": "0",
            "__d": "www",
            "__user": "0",
            "__a": "1",
            "__req": "b",
            "__hs": "20183.HYP:instagram_web_pkg.2.1...0",
            "dpr": "3",
            "__ccg": "GOOD",
            "__rev": "1021613311",
            "__s": "hm5eih:ztapmw:x0losd",
            "__hsi": "7489787314313612244",
            "__dyn": "7xeUjG1mxu1syUbFp41twpUnwgU7SbzEdF8aUco2qwJw5ux609vCwjE1EE2Cw8G11wBz81s8hwGxu786a3a1YwBgao6C0Mo2swtUd8-U2zxe2GewGw9a361qw8Xxm16wa-0oa2-azo7u3C2u2J0bS1LwTwKG1pg2fwxyo6O1FwlA3a3zhA6bwIxe6V8aUuwm8jwhU3cyVrDyo",
            "__csr": "goMJ6MT9Z48KVkIBBvRfqKOkinBtG-FfLaRgG-lZ9Qji9XGexh7VozjHRKq5J6KVqjQdGl2pAFmvK5GWGXyk8h9GA-m6V5yF4UWagnJzazAbZ5osXuFkVeGCHG8GF4l5yp9oOezpo88PAlZ1Pxa5bxGQ7o9VrFbg-8wwxp1G2acxacGVQ00jyoE0ijonyXwfwEnwWwkA2m0dLw3tE1I80hCg8UeU4Ohox0clAhAtsM0iCA9wap4DwhS1fxW0fLhpRB51m13xC3e0h2t2H801HQw1bu02j-",
            "__comet_req": "7",
            "lsd": "AVrqPT0gJDo",
            "jazoest": "2946",
            "__spin_r": "1021613311",
            "__spin_b": "trunk",
            "__spin_t": "1743852001",
            "__crn": "comet.igweb.PolarisPostRoute",
            "fb_api_caller_class": "RelayModern",
            "fb_api_req_friendly_name": "PolarisPostActionLoadPostQueryQuery",
            "variables": json.dumps(
                {
                    "shortcode": shortcode,
                    "fetch_tagged_user_count": None,
                    "hoisted_comment_id": None,
                    "hoisted_reply_id": None,
                }
            ),
            "server_timestamps": "true",
            "doc_id": "8845758582119845",
        },
        doseq=True,
    ).encode("utf-8")


def fetch_instagram_media(url: str) -> str:
    print("ENTERED fetch_instagram_media", flush=True)
    shortcode = extract_shortcode(url)

    if yt_dlp is None:
        print("yt_dlp is not available")

    if yt_dlp is not None:
        try:
            with yt_dlp.YoutubeDL({"quiet": True, "skip_download": True, "noplaylist": True}) as ydl:
                info = ydl.extract_info(url, download=False)
            if isinstance(info, dict):
                formats = info.get("formats") or []

                for fmt in reversed(formats):
                    if (
                        fmt.get("vcodec") not in (None, "none")
                        and fmt.get("acodec") not in (None, "none")
                    ):
                        return fmt["url"]

                if info.get("url"):
                    return info.get("url")

                raise RuntimeError("No format containing audio and video found.")
            raise RuntimeError("No downloadable video URL was found")
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"yt-dlp fallback failed: {exc}") from exc

    request_url = "https://www.instagram.com/graphql/query"

    headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 11; SAMSUNG SM-G973U) AppleWebKit/537.36 (KHTML, like Gecko) SamsungBrowser/14.2 Chrome/87.0.4280.141 Mobile Safari/537.36",
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.5",
        "Content-Type": "application/x-www-form-urlencoded",
        "X-FB-Friendly-Name": "PolarisPostActionLoadPostQueryQuery",
        "X-BLOKS-VERSION-ID": "0d99de0d13662a50e0958bcb112dd651f70dea02e1859073ab25f8f2a477de96",
        "X-CSRFToken": "uy8OpI1kndx4oUHjlHaUfu",
        "X-IG-App-ID": "1217981644879628",
        "X-FB-LSD": "AVrqPT0gJDo",
        "X-ASBD-ID": "359341",
        "Sec-GPC": "1",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "Pragma": "no-cache",
        "Cache-Control": "no-cache",
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

    if not isinstance(payload, dict):
        raise RuntimeError(f"Unexpected Instagram payload format: {type(payload).__name__}")

    data = payload.get("data")
    if not isinstance(data, dict):
        errors = payload.get("errors")
        detail = json.dumps(payload, ensure_ascii=False)[:1000]
        if errors:
            raise RuntimeError(f"Instagram returned an error: {errors}")
        raise RuntimeError(f"Post not found or not accessible. Response: {detail}")

    media = data.get("xdt_shortcode_media") or data.get("shortcode_media")
    if not isinstance(media, dict):
        detail = json.dumps(payload, ensure_ascii=False)[:1000]
        raise RuntimeError(f"Instagram response did not contain video media data. Response: {detail}")
    if not media.get("is_video"):
        raise RuntimeError("The URL does not point to a video")

    video_url = media.get("video_url")
    if not video_url:
        raise RuntimeError("Video URL not found in Instagram response")

    return video_url


def download_file(url: str, output_path: Path) -> None:
    headers = {
        "User-Agent": "Mozilla/5.0",
    }
    req = Request(url, headers=headers)

    try:
        with urlopen(req, timeout=60) as response, output_path.open("wb") as file_handle:
            shutil.copyfileobj(response, file_handle)
    except HTTPError as exc:
        raise RuntimeError(f"Download failed with status {exc.code}") from exc
    except URLError as exc:
        raise RuntimeError(f"Download network error: {exc}") from exc


def select_yt_dlp_format(info: dict) -> str | None:
    formats = info.get("formats") or []
    if not formats:
        return None

    combined_formats = [
        fmt
        for fmt in formats
        if fmt.get("vcodec") not in (None, "none") and fmt.get("acodec") not in (None, "none")
    ]
    if combined_formats:
        combined_formats.sort(key=lambda fmt: (fmt.get("tbr") or 0, fmt.get("height") or 0), reverse=True)
        return combined_formats[0].get("format_id")

    return "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]"


def find_ffmpeg_binary() -> str | None:
    ffmpeg_binary = shutil.which("ffmpeg") or shutil.which("ffmpeg.exe")
    if ffmpeg_binary:
        return ffmpeg_binary

    if imageio_ffmpeg is not None:
        try:
            return imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:  # noqa: BLE001
            return None

    return None


def has_gstreamer() -> bool:
    return shutil.which("gst-launch-1.0") is not None


def download_with_gstreamer(url: str, output_path: Path) -> Path:
    if yt_dlp is None:
        raise RuntimeError("yt-dlp is required for the GStreamer path")

    if not has_gstreamer():
        raise RuntimeError("GStreamer is not installed or gst-launch-1.0 is not on PATH")

    try:
        with yt_dlp.YoutubeDL({"quiet": True, "skip_download": True, "noplaylist": True}) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"yt-dlp metadata lookup failed: {exc}") from exc

    if not isinstance(info, dict):
        raise RuntimeError("yt-dlp metadata lookup failed")

    formats = info.get("formats") or []
    video_formats = [
        fmt
        for fmt in formats
        if fmt.get("vcodec") not in (None, "none") and fmt.get("acodec") in (None, "none")
    ]
    audio_formats = [
        fmt
        for fmt in formats
        if fmt.get("vcodec") in (None, "none") and fmt.get("acodec") not in (None, "none")
    ]

    if not video_formats or not audio_formats:
        raise RuntimeError("No separate video/audio formats were found for GStreamer muxing")

    best_video = max(video_formats, key=lambda fmt: (fmt.get("height") or 0, fmt.get("tbr") or 0))
    best_audio = max(audio_formats, key=lambda fmt: fmt.get("tbr") or 0)

    with tempfile.TemporaryDirectory(prefix="ig-gst-", dir=str(output_path.parent)) as temp_dir:
        temp_dir_path = Path(temp_dir)
        temp_video_path = temp_dir_path / "video.mp4"
        temp_audio_path = temp_dir_path / "audio.m4a"

        video_opts = {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "format": best_video.get("format_id"),
            "outtmpl": str(temp_video_path),
            "restrictfilenames": True,
        }
        audio_opts = {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "format": best_audio.get("format_id"),
            "outtmpl": str(temp_audio_path),
            "restrictfilenames": True,
        }

        with yt_dlp.YoutubeDL(video_opts) as ydl:
            ydl.download([url])
        with yt_dlp.YoutubeDL(audio_opts) as ydl:
            ydl.download([url])

        command = (
            f'gst-launch-1.0 -e filesrc location="{temp_video_path}" ! qtdemux name=demux '
            'demux.video_0 ! queue ! h264parse ! avdec_h264 ! videoconvert ! x264enc ! mp4mux name=mux ! filesink location="'
            f'{output_path}" demux.audio_0 ! queue ! aacparse ! avdec_aac ! audioconvert ! audioresample ! voaacenc ! mux.'
        )

        completed = subprocess.run(command, shell=True, capture_output=True, text=True)
        if completed.returncode != 0:
            stderr = completed.stderr.strip() or completed.stdout.strip() or "unknown GStreamer error"
            raise RuntimeError(f"GStreamer muxing failed: {stderr}")

    return output_path


def download_instagram_post(url: str, output_path: Path) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if yt_dlp is not None:
        if has_gstreamer():
            try:
                return download_with_gstreamer(url, output_path)
            except Exception as exc:  # noqa: BLE001
                print(f"GStreamer path failed: {exc}", file=sys.stderr)

        options = {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "outtmpl": str(output_path),
            "restrictfilenames": True,
        }

        ffmpeg_path = find_ffmpeg_binary()
        if ffmpeg_path:
            options["ffmpeg_location"] = ffmpeg_path

        try:
            with yt_dlp.YoutubeDL({**options, "skip_download": True}) as ydl:
                info = ydl.extract_info(url, download=False)
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"yt-dlp metadata lookup failed: {exc}") from exc

        selected_format = None
        if isinstance(info, dict):
            selected_format = select_yt_dlp_format(info)

        if selected_format:
            options["format"] = selected_format
        else:
            options["format"] = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]"
            options["merge_output_format"] = "mp4"

        with yt_dlp.YoutubeDL(options) as ydl:
            ydl.download([url])
        return output_path

    video_url = fetch_instagram_media(url)
    download_file(video_url, output_path)
    return output_path


# main fn\


# def main():
#     url = "https://www.instagram.com/p/C3cKS8NvVLu/"
#     output_path = Path("downloaded_video.mp4")

#     try:
#         downloaded_file = download_instagram_post(url, output_path)
#         print(f"Video downloaded successfully: {downloaded_file}")
#     except Exception as e:
#         print(f"Error: {e}")
#         sys.exit(1)

# if __name__ == "__main__":
#     main()