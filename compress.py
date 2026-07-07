# Check if video size is less than or equal to 10MB

import os
import shutil
import av

def check_video_size(file_path):
    file_size_bytes = os.path.getsize(file_path)
    file_size_mb = file_size_bytes / (1024 * 1024)
    return file_size_mb <= 10


def has_ffmpeg():
    return shutil.which("ffmpeg") is not None




def compress_video(input_path, output_path, bitrate="4000k"):
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




def compressmain():
    folder_path = "downloads"
    os.makedirs(folder_path, exist_ok=True)

    for filename in os.listdir(folder_path):
        file_path = os.path.join(folder_path, filename)
        if os.path.isfile(file_path):
            if check_video_size(file_path):
                print(f"{filename} is less than or equal to 10 MB.")
            else:
                print(f"{filename} is larger than 10 MB. Compressing...")
                compressed_file_path = os.path.join(folder_path, f"compressed_{filename}")
                compress_video(file_path, compressed_file_path)
                print(f"Compressed video saved as: {compressed_file_path}")


