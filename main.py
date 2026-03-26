"""
IB AI Agent System — Main Entry Point

FastAPI + python-telegram-bot with webhook integration, rate limiting,
and all 14 Telegram commands. Designed for Railway deployment.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Dict

from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse, PlainTextResponse
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters

from ai_engine import ai_engine
from config import settings
from database import get_all_quota_today, get_conversation_history, init_db
from handlers.business_tools import ContentGenerator, IdeaValidator, RevenueTracker
from handlers.ib_core import CASHandler, EEHandler, TOKHandler
from handlers.ib_subjects import (
    BusinessHandler,
    EconHandler,
    ESSHandler,
    EnglishHandler,
    MathHandler,
    SpanishHandler,
)
from handlers.study_planner import StudyPlanner

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
logger = logging.getLogger("ib-agent")

# ─── Rate Limiting ───

_rate_limit_store: Dict[int, deque] = {}
RATE_LIMIT_MAX = 20
RATE_LIMIT_WINDOW = 60  # seconds


def _is_rate_limited(user_id: int) -> bool:
    """Check if user has exceeded 20 requests per 60-second rolling window."""
    now = time.time()
    if user_id not in _rate_limit_store:
        _rate_limit_store[user_id] = deque()
    timestamps = _rate_limit_store[user_id]
    while timestamps and timestamps[0] < now - RATE_LIMIT_WINDOW:
        timestamps.popleft()
    if len(timestamps) >= RATE_LIMIT_MAX:
        return True
    timestamps.append(now)
    return False


# ─── Telegram Bot ───

tg_app: Application = None

# Handler instances
math_handler = MathHandler()
business_handler = BusinessHandler()
econ_handler = EconHandler()
ess_handler = ESSHandler()
spanish_handler = SpanishHandler()
english_handler = EnglishHandler()
tok_handler = TOKHandler()
cas_handler = CASHandler()
ee_handler = EEHandler()
idea_validator = IdeaValidator()
revenue_tracker = RevenueTracker()
content_generator = ContentGenerator()
study_planner = StudyPlanner()


def _is_authorized(user_id: int) -> bool:
    """Check if user is in the allowlist. Empty list = allow all."""
    if not settings.allowed_user_ids:
        return True
    return user_id in settings.allowed_user_ids


async def _split_and_reply(update: Update, text: str) -> None:
    """Send text, splitting at newlines if over Telegram's 4096 char limit."""
    max_len = 4096
    if len(text) <= max_len:
        await update.message.reply_text(text, parse_mode="Markdown")
        return
    chunks = []
    current = ""
    for line in text.split("\n"):
        if len(current) + len(line) + 1 > max_len:
            chunks.append(current)
            current = line
        else:
            current = f"{current}\n{line}" if current else line
    if current:
        chunks.append(current)
    for chunk in chunks:
        await update.message.reply_text(chunk, parse_mode="Markdown")


async def _handle_command(update: Update, context, handler_func, *args) -> None:
    """Common command handler with auth, rate limiting, and error handling."""
    user = update.effective_user
    if user is None:
        return
    if not _is_authorized(user.id):
        return
    if _is_rate_limited(user.id):
        await update.message.reply_text("⏳ Slow down — 20 requests/minute limit")
        return
    try:
        text = update.message.text or ""
        parts = text.split(maxsplit=1)
        arg_str = parts[1] if len(parts) > 1 else ""
        if arg_str:
            result = await handler_func(arg_str.strip(), user.id, *args)
        else:
            result = await handler_func(user.id, *args)
        await _split_and_reply(update, result)
    except Exception as exc:
        logger.error("Command error: %s", exc, exc_info=True)
        await update.message.reply_text(f"❌ Error: {exc}")


# ─── Command Handlers ───


async def cmd_start(update: Update, context) -> None:
    """Handle /start — inline welcome message with command list."""
    user = update.effective_user
    if user is None or not _is_authorized(user.id):
        return
    welcome = (
        "🎓 **IB AI Agent** — Your Personal IB Tutor\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "**📚 IB Subjects**\n"
        "/math `<problem>` — Solve Math AA HL problems\n"
        "/markscheme `<question>` — Generate IB mark scheme\n"
        "/essay `<question>` — Business HL essay structure\n"
        "/econ `<question>` — Economics diagram + analysis\n"
        "/ess `<concept>` — ESS concept explanation\n"
        "/spanish `<text>` — Spanish grammar check\n"
        "/english `<extract>` — Paper 1 analysis\n\n"
        "**🎯 IB Core**\n"
        "/tok `<rls>` — TOK knowledge questions\n"
        "/cas — CAS project ideas\n"
        "/ee `<topic>` — Extended Essay RQ refinement\n\n"
        "**💼 Business Tools**\n"
        "/validate `<idea>` — Validate a business idea\n"
        "/study — Review due flashcards\n\n"
        "**📊 System**\n"
        "/quota — AI provider status + quota\n\n"
        "Type any command to get started! 🚀"
    )
    await update.message.reply_text(welcome, parse_mode="Markdown")


async def cmd_math(update: Update, context) -> None:
    """Handle /math <problem>."""
    async def handler(arg: str, uid: int) -> str:
        return await math_handler.solve(arg, uid)
    await _handle_command(update, context, handler)


async def cmd_markscheme(update: Update, context) -> None:
    """Handle /markscheme <question>."""
    async def handler(arg: str, uid: int) -> str:
        return await math_handler.mark_scheme(arg, uid)
    await _handle_command(update, context, handler)


async def cmd_essay(update: Update, context) -> None:
    """Handle /essay <question>."""
    async def handler(arg: str, uid: int) -> str:
        return await business_handler.essay_structure(arg, uid)
    await _handle_command(update, context, handler)


async def cmd_econ(update: Update, context) -> None:
    """Handle /econ <question>."""
    async def handler(arg: str, uid: int) -> str:
        return await econ_handler.diagram_explain("supply and demand", arg, uid)
    await _handle_command(update, context, handler)


async def cmd_ess(update: Update, context) -> None:
    """Handle /ess <concept>."""
    async def handler(arg: str, uid: int) -> str:
        return await ess_handler.concept_explain(arg, uid)
    await _handle_command(update, context, handler)


async def cmd_spanish(update: Update, context) -> None:
    """Handle /spanish <text>."""
    async def handler(arg: str, uid: int) -> str:
        return await spanish_handler.grammar_check(arg, uid)
    await _handle_command(update, context, handler)


async def cmd_english(update: Update, context) -> None:
    """Handle /english <extract>."""
    async def handler(arg: str, uid: int) -> str:
        return await english_handler.paper1_analysis("prose", arg, uid)
    await _handle_command(update, context, handler)


async def cmd_tok(update: Update, context) -> None:
    """Handle /tok <rls>."""
    async def handler(arg: str, uid: int) -> str:
        return await tok_handler.knowledge_question(arg, uid)
    await _handle_command(update, context, handler)


async def cmd_cas(update: Update, context) -> None:
    """Handle /cas."""
    async def handler(uid: int) -> str:
        return await cas_handler.project_ideas(150, "general interests", uid)
    await _handle_command(update, context, handler)


async def cmd_ee(update: Update, context) -> None:
    """Handle /ee <topic>."""
    async def handler(arg: str, uid: int) -> str:
        return await ee_handler.rq_refine("General", arg, uid)
    await _handle_command(update, context, handler)


async def cmd_validate(update: Update, context) -> None:
    """Handle /validate <idea>."""
    async def handler(arg: str, uid: int) -> str:
        return await idea_validator.validate(arg, "General", uid)
    await _handle_command(update, context, handler)


async def cmd_study(update: Update, context) -> None:
    """Handle /study — review due flashcards."""
    async def handler(uid: int) -> str:
        return await study_planner.review_due(uid)
    await _handle_command(update, context, handler)


async def cmd_quota(update: Update, context) -> None:
    """Handle /quota — show AI provider status."""
    user = update.effective_user
    if user is None or not _is_authorized(user.id):
        return
    status = await ai_engine.health_status()
    lines = ["📊 **AI Provider Status**\n"]
    for provider, info in status["providers"].items():
        icon = "🟢" if info["online"] else "🔴"
        limit_str = f"/{info['quota_limit']}" if info["quota_limit"] else "∞"
        lines.append(
            f"{icon} **{provider.title()}**: {info['quota_used']}{limit_str} used today"
        )
    lines.append(f"\n💾 Cache: {status['cache_size']}/{status['cache_max']} items")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def cmd_unknown(update: Update, context) -> None:
    """Handle unknown commands."""
    user = update.effective_user
    if user is None or not _is_authorized(user.id):
        return
    await update.message.reply_text(
        "❓ Unknown command. Type /start to see available commands."
    )


# ─── Telegram Application Setup ───


def build_telegram_app() -> Application:
    """Build and configure the Telegram bot application."""
    app = Application.builder().token(settings.telegram_bot_token).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("math", cmd_math))
    app.add_handler(CommandHandler("markscheme", cmd_markscheme))
    app.add_handler(CommandHandler("essay", cmd_essay))
    app.add_handler(CommandHandler("econ", cmd_econ))
    app.add_handler(CommandHandler("ess", cmd_ess))
    app.add_handler(CommandHandler("spanish", cmd_spanish))
    app.add_handler(CommandHandler("english", cmd_english))
    app.add_handler(CommandHandler("tok", cmd_tok))
    app.add_handler(CommandHandler("cas", cmd_cas))
    app.add_handler(CommandHandler("ee", cmd_ee))
    app.add_handler(CommandHandler("validate", cmd_validate))
    app.add_handler(CommandHandler("study", cmd_study))
    app.add_handler(CommandHandler("quota", cmd_quota))
    app.add_handler(MessageHandler(filters.COMMAND, cmd_unknown))

    return app


# ─── FastAPI App ───


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    global tg_app

    logger.info("🔧 Initializing database...")
    await init_db()
    logger.info("✅ Database ready")

    logger.info("🔧 Warming up AI providers...")
    provider_status = await ai_engine.warmup()
    online = [k for k, v in provider_status.items() if v]
    offline = [k for k, v in provider_status.items() if not v]
    logger.info("🟢 Online: %s", ", ".join(online) or "none")
    logger.info("🔴 Offline: %s", ", ".join(offline) or "none")

    logger.info("🔧 Starting Telegram bot...")
    tg_app = build_telegram_app()
    await tg_app.initialize()
    await tg_app.start()

    if settings.webhook_url:
        webhook_url = f"{settings.webhook_url}/webhook"
        logger.info("🔧 Registering webhook: %s", webhook_url)
        await tg_app.bot.set_webhook(
            url=webhook_url,
            secret_token=settings.webhook_secret,
        )
        logger.info("✅ Webhook registered")
    else:
        logger.warning("⚠️ WEBHOOK_URL not set — bot will not receive updates")

    logger.info(
        "🚀 IB Agent System ready | port=%s | db=%s",
        settings.port,
        settings.db_path,
    )

    yield

    logger.info("🛑 Shutting down...")
    if tg_app:
        await tg_app.stop()
        await tg_app.shutdown()


app = FastAPI(title="IB AI Agent System", lifespan=lifespan)


@app.post("/webhook")
async def telegram_webhook(request: Request) -> dict:
    """Handle incoming Telegram webhook updates."""
    secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if secret != settings.webhook_secret:
        return {"ok": False, "error": "unauthorized"}

    try:
        data = await request.json()
        update = Update.de_json(data, tg_app.bot)
        await tg_app.process_update(update)
    except Exception as exc:
        logger.error("Webhook error: %s", exc, exc_info=True)

    return {"ok": True}


@app.get("/health")
async def health_check() -> dict:
    """Health endpoint for Railway. Returns 200 even if some providers are down."""
    from database import get_db

    db_ok = True
    try:
        async with get_db() as db:
            await db.execute("SELECT 1")
    except Exception:
        db_ok = False

    status = await ai_engine.health_status()
    quota = await get_all_quota_today()

    return {
        "status": "healthy",
        "db": "ok" if db_ok else "error",
        "providers": {
            k: v["online"] for k, v in status["providers"].items()
        },
        "quota": quota,
    }


@app.get("/", response_class=HTMLResponse)
async def dashboard() -> str:
    """Inline HTML dashboard showing system status."""
    status = await ai_engine.health_status()
    quota = await get_all_quota_today()

    provider_rows = ""
    for name, info in status["providers"].items():
        icon = "🟢" if info["online"] else "🔴"
        limit = info["quota_limit"] or "∞"
        provider_rows += (
            f"<tr><td>{icon} {name.title()}</td>"
            f"<td>{info['quota_used']} / {limit}</td></tr>"
        )

    conv_count = len(quota)

    html = f"""<!DOCTYPE html>
<html><head><title>IB Agent Dashboard</title>
<style>
  body {{ font-family: -apple-system, sans-serif; max-width: 600px; margin: 40px auto; padding: 0 20px; }}
  h1 {{ color: #1a1a2e; }}
  table {{ border-collapse: collapse; width: 100%; margin: 16px 0; }}
  th, td {{ border: 1px solid #ddd; padding: 10px; text-align: left; }}
  th {{ background: #f5f5f5; }}
  .status {{ padding: 4px 12px; border-radius: 12px; font-size: 14px; }}
  .ok {{ background: #d4edda; color: #155724; }}
</style></head><body>
<h1>🎓 IB Agent System</h1>
<p><span class="status ok">Healthy</span></p>
<h2>AI Providers</h2>
<table><tr><th>Provider</th><th>Quota (today)</th></tr>{provider_rows}</table>
<h2>Cache</h2>
<p>{status['cache_size']} / {status['cache_max']} items</p>
</body></html>"""
    return html


@app.get("/metrics", response_class=PlainTextResponse)
async def metrics() -> str:
    """Prometheus-style metrics endpoint."""
    status = await ai_engine.health_status()
    quota = await get_all_quota_today()

    lines = [
        "# HELP requests_total Total API requests today",
        "# TYPE requests_total counter",
    ]

    total = sum(quota.values())
    lines.append(f"requests_total {total}")

    lines.append("# HELP ai_provider_calls_total AI calls by provider")
    lines.append("# TYPE ai_provider_calls_total counter")
    for provider, count in quota.items():
        lines.append(f'ai_provider_calls_total{{provider="{provider}"}} {count}')

    lines.append("# HELP quota_remaining Remaining quota by provider")
    lines.append("# TYPE quota_remaining gauge")
    for name, info in status["providers"].items():
        if info["quota_limit"] is not None:
            remaining = info["quota_limit"] - info["quota_used"]
            lines.append(f'quota_remaining{{provider="{name}"}} {remaining}')

    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.port,
        log_level=settings.log_level.lower(),
    )
