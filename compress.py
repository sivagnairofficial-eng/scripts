# Check if video size is less than or equal to 10MB

import os
import shutil
import tempfile
import av
import subprocess

from download_instagram_video import find_ffmpeg_binary


ffmpeg_loc = os.environ.get("FFMPEG_LOC", "")


def resolve_ffmpeg_executable():
    ffmpeg_exec = find_ffmpeg_binary()
    if ffmpeg_exec:
        return ffmpeg_exec

    ffmpeg_exec = shutil.which("ffmpeg") or shutil.which("ffmpeg.exe")
    if ffmpeg_exec:
        return ffmpeg_exec

    env_path = os.environ.get("FFMPEG_PATH")
    if env_path and os.path.exists(env_path):
        return env_path

    candidates = []
    if ffmpeg_loc:
        if os.name == "nt":
            candidates.append(os.path.join(ffmpeg_loc, "ffmpeg.exe"))
        else:
            candidates.append(os.path.join(ffmpeg_loc, "ffmpeg"))

    candidates.extend([
        "/usr/bin/ffmpeg",
        "/usr/local/bin/ffmpeg",
    ])

    for candidate in candidates:
        if candidate and os.path.exists(candidate):
            return candidate

    return None


def check_video_size(file_path):
    file_size_bytes = os.path.getsize(file_path)
    file_size_mb = file_size_bytes / (1024 * 1024)
    return file_size_mb <= 10


def has_ffmpeg():
    return resolve_ffmpeg_executable() is not None


def recompress_video(input_path, output_path):
    ffmpeg_exec = resolve_ffmpeg_executable()
    if not ffmpeg_exec:
        raise FileNotFoundError("ffmpeg executable not found")

    cmd = [
        ffmpeg_exec,
        "-y",
        "-i", input_path,

        # Video
        "-c:v", "libx264",
        "-preset", "veryslow",
        "-crf", "35",
        "-vf", "scale='min(640,iw)':-2",
        "-r", "15",

        # Audio
        "-c:a", "aac",
        "-b:a", "64k",

        # Optimize MP4
        "-movflags", "+faststart",

        output_path,
    ]

    subprocess.run(cmd, check=True)

def compress_video_pyav(input_path, output_path, bitrate="3500k"):
    input_container = av.open(input_path)

    output_container = av.open(output_path, mode="w")

    input_video = input_container.streams.video[0]

    output_video = output_container.add_stream(
        "libx264",
        rate=input_video.average_rate,
    )

    output_video.width = input_video.width
    output_video.height = input_video.height
    output_video.pix_fmt = "yuv420p"
    output_video.bit_rate = int(bitrate[:-1]) * 1000

    for frame in input_container.decode(video=0):
        packet = output_video.encode(frame)
        if packet:
            output_container.mux(packet)

    # Flush encoder
    for packet in output_video.encode():
        output_container.mux(packet)

    input_container.close()
    output_container.close()


def compress_video_ffmpeg(input_path, output_path, bitrate="3500k", target_size_mb=10):
    ffmpeg_exec = resolve_ffmpeg_executable()
    print(f"Using ffmpeg: {ffmpeg_exec}")
    if not ffmpeg_exec:
        raise FileNotFoundError("ffmpeg executable not found")

    target_size_bytes = int(target_size_mb * 1024 * 1024)
    bitrate_value = int(bitrate[:-1]) if bitrate.endswith("k") else int(bitrate)
    current_bitrate = bitrate_value

    while True:
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as temp_file:
            temp_output_path = temp_file.name

        try:
            cmd = [
                ffmpeg_exec,
                "-y",
                "-i",
                input_path,
                "-c:v",
                "libx264",
                "-b:v",
                f"{current_bitrate}k",
                "-preset",
                "veryfast",
                "-pix_fmt",
                "yuv420p",
                "-fs",
                str(target_size_bytes),
                temp_output_path,
            ]

            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if result.returncode != 0:
                raise RuntimeError(f"ffmpeg failed: {result.stderr.decode(errors='ignore')}")

            if os.path.exists(temp_output_path):
                actual_size = os.path.getsize(temp_output_path)
                if actual_size <= target_size_bytes:
                    if os.path.exists(output_path):
                        os.remove(output_path)
                    os.replace(temp_output_path, output_path)
                    return

            if os.path.exists(temp_output_path):
                os.remove(temp_output_path)

            if current_bitrate <= 500:
                raise RuntimeError(f"Unable to compress video to {target_size_mb}MB or less")

            current_bitrate = max(500, int(current_bitrate * 0.9))
        except Exception:
            if os.path.exists(temp_output_path):
                os.remove(temp_output_path)
            raise


def compress_video(input_path, output_path, bitrate="4000k", target_size_mb=10):
    if has_ffmpeg():
        try:
            compress_video_ffmpeg(input_path, output_path, bitrate=bitrate, target_size_mb=target_size_mb)
            return
        except Exception:
            # If ffmpeg fails, fall back to PyAV implementation
            pass

    compress_video_pyav(input_path, output_path, bitrate=bitrate)




# def compressmain():
#     folder_path = "downloads"
#     os.makedirs(folder_path, exist_ok=True)

#     for filename in os.listdir(folder_path):
#         file_path = os.path.join(folder_path, filename)
#         if os.path.isfile(file_path):
#             if check_video_size(file_path):
#                 print(f"{filename} is less than or equal to 10 MB.")
#             else:
#                 print(f"{filename} is larger than 10 MB. Compressing...")
#                 compressed_file_path = os.path.join(folder_path, f"compressed_{filename}")
#                 try:
#                     compress_video(file_path, compressed_file_path)
#                     print(f"Compressed video saved as: {compressed_file_path}")
#                 except Exception as e:
#                     print(f"Compression failed for {filename}: {e}")



# compressmain()
