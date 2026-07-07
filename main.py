import asyncio
from pathlib import Path
import discord
from discord.ext import commands
import download_instagram_video
import datetime
import os


TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)



@bot.command(name="reel")
async def reel(ctx, link: str):
    username = ctx.author.name
    
    fetched_video_path = await fetch_reels_video(link, username)
    await send_video(ctx, fetched_video_path)

    await ctx.message.delete()
   
    if Path(fetched_video_path).exists():
        os.remove(fetched_video_path)


    
  

async def fetch_reels_video(url, username):
    return await asyncio.to_thread(process_video, url, username)

def process_video(url, username):
    download_dir = Path("download")
    download_dir.mkdir(parents=True, exist_ok=True)

    temp_file_path = Path(f"download/{username}_{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}_temp_video.mp4")
    download_instagram_video.download_instagram_post(url, temp_file_path)

    return temp_file_path


async def send_video(ctx, video_path):
    await ctx.send(file=discord.File(video_path))
import os


bot.run(TOKEN)
