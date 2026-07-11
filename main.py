import asyncio
from pathlib import Path
import discord
from discord.ext import commands
import download_instagram_video
import datetime
import os
import shutil
import compress

TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)



@bot.command(name="reel")
async def reel(ctx, link: str):
    username = ctx.author.name
    
    fetched_video_path = await fetch_reels_video(link, username)
    try:
        await send_video(ctx, fetched_video_path)
       
        await ctx.message.delete()
        
        flush_download_folder()
        
        if not is_download_folder_empty():
            print("Download folder is not empty")
   
    except Exception as e:
        size = os.path.getsize(fetched_video_path)
        await ctx.message.delete()
        await ctx.send(f"File is more than 10MB.It is {size} after compression")
        flush_download_folder()
   

async def fetch_reels_video(url, username):
    return await asyncio.to_thread(process_video, url, username)


def is_download_folder_empty(download_dir="download"):
    download_path = Path(download_dir)
    download_path.mkdir(parents=True, exist_ok=True)
    return not any(download_path.iterdir())  

def flush_download_folder(download_dir="download"):
    download_path = Path(download_dir)
    download_path.mkdir(parents=True, exist_ok=True)

    for item in download_path.iterdir():
        if item.is_file() or item.is_symlink():
            item.unlink()
        elif item.is_dir():
            shutil.rmtree(item)
            
    print("FLUSHED!!!!!")
    return download_path


def process_video(url, username):
    download_dir = Path("download")
    download_dir.mkdir(parents=True, exist_ok=True)

    temp_file_path = Path(f"download/{username}_{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}_temp_video.mp4")
    download_instagram_video.download_instagram_post(url, temp_file_path)
    compress_path = Path(f"download/{username}_{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}_compressed_video.mp4")
    if compress.check_video_size(temp_file_path):
                    print(f"{temp_file_path} is less than or equal to 10 MB.")
    else:
        size = os.path.getsize(temp_file_path)
        print(f"{temp_file_path} is larger than 10 MB.{size} MB Compressing...")
        
        try:
            compress.compress_video(temp_file_path, compress_path)
            print(f"Compressed video saved as: {compress_path}")
              
           
            if compress.check_video_size(compress_path):
                    print(f"{compress_path} is less than or equal to 10 MB ++++++")
            else:
                size = os.path.getsize(compress_path)
                print(f"{compress_path} is more than  10 MB.!!!!!! Further compressing {size}")
                os.remove(compress_path)
                compress.compress_video(temp_file_path, compress_path)
                
            temp_file_path = compress_path    
        except Exception as e:
            print(f"Compression failed for {temp_file_path}: {e}")


    return temp_file_path


async def send_video(ctx, video_path):
    await ctx.send(file=discord.File(video_path))
import os


bot.run(TOKEN)
