import discord
from discord.ext import commands
import asyncio
import os

# Import your existing handlers
from handlers.ib_subjects import MathHandler, BusinessHandler, EconHandler, ESSHandler, SpanishHandler, EnglishHandler
from handlers.ib_core import TOKHandler, CASHandler, EEHandler
from handlers.study_planner import StudyPlanner
from handlers.business_tools import IdeaValidator, RevenueTracker
from config import settings

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="/", intents=intents, help_command=None)

@bot.event
async def on_ready():
    print(f'🎓 IB Bot logged in as {bot.user}')
    print(f'Bot is in {len(bot.guilds)} servers')

@bot.command(name="math")
async def math_cmd(ctx, *, problem: str):
    """Solve IB Math AA HL problems."""
    async with ctx.typing():
        handler = MathHandler()
        response = await handler.solve(problem)
        
        # Discord has 2000 char limit
        if len(response) > 1900:
            response = response[:1900] + "\n\n... (truncated, use shorter problem)"
        
        embed = discord.Embed(
            title="📐 Math Solution",
            description=response,
            color=0x667eea
        )
        embed.set_footer(text="IB AI Tutor • Math AA HL")
        await ctx.send(embed=embed)

@bot.command(name="business")
async def business_cmd(ctx, *, question: str):
    """Business Management HL help."""
    async with ctx.typing():
        handler = BusinessHandler()
        response = await handler.handle(question)
        
        embed = discord.Embed(
            title="💼 Business Essay Help",
            description=response[:1900],
            color=0x00d4aa
        )
        await ctx.send(embed=embed)

@bot.command(name="econ")
async def econ_cmd(ctx, *, topic: str):
    """Economics HL help with diagrams."""
    async with ctx.typing():
        handler = EconHandler()
        response = await handler.handle(topic)
        
        embed = discord.Embed(
            title="📊 Economics",
            description=response[:1900],
            color=0xff6b6b
        )
        await ctx.send(embed=embed)

@bot.command(name="study")
async def study_cmd(ctx, *, args: str = "plan today"):
    """Study planner."""
    async with ctx.typing():
        planner = StudyPlanner()
        
        if "plan" in args:
            response = await planner.get_plan(ctx.author.id)
        elif "stats" in args:
            response = await planner.get_stats(ctx.author.id)
        else:
            response = "Usage: /study plan today | /study stats"
        
        embed = discord.Embed(
            title="📚 Study Planner",
            description=response,
            color=0xffd93d
        )
        await ctx.send(embed=embed)

@bot.command(name="cas")
async def cas_cmd(ctx, hours: int = 10, *, interests: str = ""):
    """CAS project ideas."""
    async with ctx.typing():
        handler = CASHandler()
        response = await handler.project_ideas(hours, interests)
        
        embed = discord.Embed(
            title="🎯 CAS Project Ideas",
            description=response,
            color=0xa855f7
        )
        await ctx.send(embed=embed)

@bot.command(name="tok")
async def tok_cmd(ctx, *, rls: str):
    """Theory of Knowledge help."""
    async with ctx.typing():
        handler = TOKHandler()
        response = await handler.knowledge_question(rls)
        
        embed = discord.Embed(
            title="🧠 TOK",
            description=response,
            color=0xec4899
        )
        await ctx.send(embed=embed)

@bot.command(name="idea")
async def idea_cmd(ctx, *, business_idea: str):
    """Validate business idea."""
    async with ctx.typing():
        validator = IdeaValidator()
        response = await validator.validate(business_idea)
        
        embed = discord.Embed(
            title="💡 Business Validator",
            description=response,
            color=0x10b981
        )
        await ctx.send(embed=embed)

@bot.command(name="help")
async def help_cmd(ctx):
    """Show all commands."""
    embed = discord.Embed(
        title="🎓 IB AI Tutor Commands",
        description="""
📐 **/math** [problem] - Solve IB Math AA HL
💼 **/business** [question] - Business essay help
📊 **/econ** [topic] - Economics diagrams & essays
🌍 **/ess** [topic] - Environmental Systems
🇪🇸 **/spanish** [topic] - Spanish AB practice
📖 **/english** [text] - English Lit analysis
🧠 **/tok** [real life situation] - TOK help
🎯 **/cas** [hours] [interests] - CAS project ideas
📝 **/ee** [topic] - Extended essay help
📚 **/study** [plan today/stats] - Study planner
💡 **/idea** [business] - Business validator
❓ **/help** - Show this message
        """,
        color=0x667eea
    )
    await ctx.send(embed=embed)

def run_discord_bot():
    """Start Discord bot."""
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        print("⚠️ DISCORD_TOKEN not set, skipping Discord bot")
        return
    
    bot.run(token)

# If running standalone
if __name__ == "__main__":
    run_discord_bot()
