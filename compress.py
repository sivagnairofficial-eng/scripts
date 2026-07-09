# Check if video size is less than or equal to 10MB

import os
import shutil
import tempfile
import av
import subprocess


ffmpeg_loc = 'C:\\Users\\sivag\\Downloads\\ffmpeg-8.1.2-essentials_build\\ffmpeg-8.1.2-essentials_build\\bin'

def check_video_size(file_path):
    file_size_bytes = os.path.getsize(file_path)
    file_size_mb = file_size_bytes / (1024 * 1024)
    return file_size_mb <= 10


def has_ffmpeg():
    if shutil.which("ffmpeg"):
        return True
    ffmpeg_path = os.path.join(ffmpeg_loc, "ffmpeg.exe")
    return os.path.exists(ffmpeg_path)




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
    # Determine ffmpeg executable
    ffmpeg_exec = shutil.which("ffmpeg")
    if not ffmpeg_exec:
        candidate = os.path.join(ffmpeg_loc, "ffmpeg.exe")
        if os.path.exists(candidate):
            ffmpeg_exec = candidate

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


