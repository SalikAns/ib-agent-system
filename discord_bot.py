import discord
from discord.ext import commands
import asyncio
import os
import threading

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="/", intents=intents, help_command=None)

@bot.event
async def on_ready():
    print(f'🎓 IB Bot logged in as {bot.user}')

@bot.command(name="math")
async def math_cmd(ctx, *, problem: str):
    """Solve math problems."""
    await ctx.send(f"📐 Math: {problem}")

@bot.command(name="help")
async def help_cmd(ctx):
    """Show help."""
    await ctx.send("Commands: /math, /business, /econ, /study, /cas")

def run_discord_bot():
    """Start Discord bot in background thread."""
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        print("⚠️ DISCORD_TOKEN not set")
        return
    
    # Run in thread so it doesn't block FastAPI
    def start_bot():
        bot.run(token)
    
    thread = threading.Thread(target=start_bot, daemon=True)
    thread.start()
    print("🎓 Discord bot started in background")

if __name__ == "__main__":
    run_discord_bot()
