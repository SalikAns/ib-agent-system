"""
IB AI Agent System — Database Module

Async SQLite database with 6 tables and full CRUD operations.
Uses aiosqlite for non-blocking database access.
"""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from datetime import date, datetime
from typing import Any, Dict, List, Optional

import aiosqlite

from config import settings

_db: Optional[aiosqlite.Connection] = None


@asynccontextmanager
async def get_db():
    """Yield an aiosqlite connection. Ensures foreign keys enabled, closes on exit."""
    db = await aiosqlite.connect(settings.db_path)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    try:
        yield db
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    finally:
        await db.close()


async def init_db() -> None:
    """Create all 6 tables if they do not exist. Idempotent — safe on every cold start."""
    async with get_db() as db:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                command TEXT NOT NULL,
                message TEXT NOT NULL,
                response TEXT NOT NULL,
                tokens_used INTEGER DEFAULT 0,
                provider TEXT DEFAULT '',
                latency_ms INTEGER DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS study_cards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                subject TEXT NOT NULL,
                topic TEXT NOT NULL,
                front TEXT NOT NULL,
                back TEXT NOT NULL,
                interval_days REAL DEFAULT 1,
                repetitions INTEGER DEFAULT 0,
                ease_factor REAL DEFAULT 2.5,
                due_date TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS business_projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                stage TEXT DEFAULT 'idea',
                revenue_total REAL DEFAULT 0,
                expenses_total REAL DEFAULT 0,
                mvp_description TEXT DEFAULT '',
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS cas_activities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                activity_name TEXT NOT NULL,
                strand TEXT NOT NULL CHECK (strand IN ('C', 'A', 'S')),
                hours REAL NOT NULL DEFAULT 0,
                reflection TEXT DEFAULT '',
                evidence_links_json TEXT DEFAULT '[]',
                activity_date TEXT NOT NULL DEFAULT (date('now'))
            );

            CREATE TABLE IF NOT EXISTS quota_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                provider TEXT NOT NULL,
                usage_date TEXT NOT NULL,
                request_count INTEGER DEFAULT 0,
                tokens_consumed INTEGER DEFAULT 0,
                UNIQUE(provider, usage_date)
            );

            CREATE TABLE IF NOT EXISTS user_preferences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE NOT NULL,
                weak_subjects_json TEXT DEFAULT '[]',
                study_hours_per_day REAL DEFAULT 3,
                learning_style TEXT DEFAULT 'visual',
                exam_dates_json TEXT DEFAULT '{}'
            );
        """)


# ─── Conversations CRUD ───


async def insert_conversation(
    user_id: int,
    command: str,
    message: str,
    response: str,
    tokens_used: int = 0,
    provider: str = "",
    latency_ms: int = 0,
) -> int:
    """Insert a conversation record and return its id."""
    async with get_db() as db:
        cursor = await db.execute(
            """INSERT INTO conversations
               (user_id, command, message, response, tokens_used, provider, latency_ms)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (user_id, command, message, response, tokens_used, provider, latency_ms),
        )
        return cursor.lastrowid


async def get_conversations_by_user(user_id: int, limit: int = 20) -> List[Dict[str, Any]]:
    """Return recent conversations for a user, newest first."""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM conversations WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_conversation_history(user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
    """Return recent conversation history as dicts for context."""
    async with get_db() as db:
        cursor = await db.execute(
            """SELECT command, message, response, created_at
               FROM conversations WHERE user_id = ?
               ORDER BY created_at DESC LIMIT ?""",
            (user_id, limit),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def update_conversation(conv_id: int, **kwargs) -> None:
    """Update fields on a conversation by id."""
    allowed = {"command", "message", "response", "tokens_used", "provider", "latency_ms"}
    fields = {k: v for k, v in kwargs.items() if k in allowed}
    if not fields:
        return
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [conv_id]
    async with get_db() as db:
        await db.execute(f"UPDATE conversations SET {set_clause} WHERE id = ?", values)


async def delete_conversation(conv_id: int) -> None:
    """Delete a conversation by id."""
    async with get_db() as db:
        await db.execute("DELETE FROM conversations WHERE id = ?", (conv_id,))


# ─── Study Cards CRUD ───


async def insert_study_card(
    user_id: int,
    subject: str,
    topic: str,
    front: str,
    back: str,
    interval_days: float = 1,
    repetitions: int = 0,
    ease_factor: float = 2.5,
) -> int:
    """Create a study card with SM-2 defaults and today as due date."""
    due = date.today().isoformat()
    async with get_db() as db:
        cursor = await db.execute(
            """INSERT INTO study_cards
               (user_id, subject, topic, front, back, interval_days, repetitions, ease_factor, due_date)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_id, subject, topic, front, back, interval_days, repetitions, ease_factor, due),
        )
        return cursor.lastrowid


async def get_study_cards_by_user(user_id: int) -> List[Dict[str, Any]]:
    """Return all study cards for a user."""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM study_cards WHERE user_id = ? ORDER BY due_date ASC",
            (user_id,),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_due_cards(user_id: int) -> List[Dict[str, Any]]:
    """Return study cards due today or earlier."""
    today = date.today().isoformat()
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM study_cards WHERE user_id = ? AND due_date <= ? ORDER BY due_date ASC",
            (user_id, today),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def update_study_card(card_id: int, **kwargs) -> None:
    """Update fields on a study card."""
    allowed = {
        "subject", "topic", "front", "back", "interval_days",
        "repetitions", "ease_factor", "due_date",
    }
    fields = {k: v for k, v in kwargs.items() if k in allowed}
    if not fields:
        return
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [card_id]
    async with get_db() as db:
        await db.execute(f"UPDATE study_cards SET {set_clause} WHERE id = ?", values)


async def delete_study_card(card_id: int) -> None:
    """Delete a study card by id."""
    async with get_db() as db:
        await db.execute("DELETE FROM study_cards WHERE id = ?", (card_id,))


# ─── Business Projects CRUD ───


async def insert_business_project(
    user_id: int,
    name: str,
    stage: str = "idea",
    revenue_total: float = 0,
    expenses_total: float = 0,
    mvp_description: str = "",
) -> int:
    """Create a new business project."""
    async with get_db() as db:
        cursor = await db.execute(
            """INSERT INTO business_projects
               (user_id, name, stage, revenue_total, expenses_total, mvp_description)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (user_id, name, stage, revenue_total, expenses_total, mvp_description),
        )
        return cursor.lastrowid


async def get_business_projects_by_user(user_id: int) -> List[Dict[str, Any]]:
    """Return all business projects for a user."""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM business_projects WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def update_business_project(project_id: int, **kwargs) -> None:
    """Update fields on a business project."""
    allowed = {"name", "stage", "revenue_total", "expenses_total", "mvp_description"}
    fields = {k: v for k, v in kwargs.items() if k in allowed}
    fields["updated_at"] = datetime.utcnow().isoformat()
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [project_id]
    async with get_db() as db:
        await db.execute(f"UPDATE business_projects SET {set_clause} WHERE id = ?", values)


async def delete_business_project(project_id: int) -> None:
    """Delete a business project by id."""
    async with get_db() as db:
        await db.execute("DELETE FROM business_projects WHERE id = ?", (project_id,))


# ─── CAS Activities CRUD ───


async def insert_cas_activity(
    user_id: int,
    activity_name: str,
    strand: str,
    hours: float,
    reflection: str = "",
    evidence_links: Optional[List[str]] = None,
    activity_date: Optional[str] = None,
) -> int:
    """Log a CAS activity."""
    links = json.dumps(evidence_links or [])
    act_date = activity_date or date.today().isoformat()
    async with get_db() as db:
        cursor = await db.execute(
            """INSERT INTO cas_activities
               (user_id, activity_name, strand, hours, reflection, evidence_links_json, activity_date)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (user_id, activity_name, strand, hours, reflection, links, act_date),
        )
        return cursor.lastrowid


async def get_cas_activities_by_user(user_id: int) -> List[Dict[str, Any]]:
    """Return all CAS activities for a user."""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM cas_activities WHERE user_id = ? ORDER BY activity_date DESC",
            (user_id,),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_cas_strand_totals(user_id: int) -> Dict[str, float]:
    """Return total hours per CAS strand."""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT strand, SUM(hours) as total FROM cas_activities WHERE user_id = ? GROUP BY strand",
            (user_id,),
        )
        rows = await cursor.fetchall()
        return {row["strand"]: row["total"] for row in rows}


async def update_cas_activity(activity_id: int, **kwargs) -> None:
    """Update fields on a CAS activity."""
    allowed = {"activity_name", "strand", "hours", "reflection", "evidence_links_json", "activity_date"}
    fields = {k: v for k, v in kwargs.items() if k in allowed}
    if not fields:
        return
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [activity_id]
    async with get_db() as db:
        await db.execute(f"UPDATE cas_activities SET {set_clause} WHERE id = ?", values)


async def delete_cas_activity(activity_id: int) -> None:
    """Delete a CAS activity by id."""
    async with get_db() as db:
        await db.execute("DELETE FROM cas_activities WHERE id = ?", (activity_id,))


# ─── Quota Usage CRUD ───


async def get_quota_today(provider: str) -> int:
    """Return request_count for a provider today. Returns 0 if no row."""
    today = date.today().isoformat()
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT request_count FROM quota_usage WHERE provider = ? AND usage_date = ?",
            (provider, today),
        )
        row = await cursor.fetchone()
        if row is None:
            return 0
        return row["request_count"]


async def increment_quota(provider: str, tokens: int = 0) -> None:
    """Upsert quota row for today: increment request_count and tokens_consumed."""
    today = date.today().isoformat()
    async with get_db() as db:
        await db.execute(
            """INSERT INTO quota_usage (provider, usage_date, request_count, tokens_consumed)
               VALUES (?, ?, 1, ?)
               ON CONFLICT(provider, usage_date)
               DO UPDATE SET request_count = request_count + 1,
                             tokens_consumed = tokens_consumed + excluded.tokens_consumed""",
            (provider, today, tokens),
        )


async def get_all_quota_today() -> Dict[str, int]:
    """Return {provider: request_count} for all providers today."""
    today = date.today().isoformat()
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT provider, request_count FROM quota_usage WHERE usage_date = ?",
            (today,),
        )
        rows = await cursor.fetchall()
        return {row["provider"]: row["request_count"] for row in rows}


# ─── User Preferences CRUD ───


async def upsert_user_preferences(
    user_id: int,
    weak_subjects: Optional[List[str]] = None,
    study_hours_per_day: Optional[float] = None,
    learning_style: Optional[str] = None,
    exam_dates: Optional[Dict[str, str]] = None,
) -> None:
    """Create or update user preferences."""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT id FROM user_preferences WHERE user_id = ?", (user_id,)
        )
        existing = await cursor.fetchone()

        if existing:
            updates = []
            values = []
            if weak_subjects is not None:
                updates.append("weak_subjects_json = ?")
                values.append(json.dumps(weak_subjects))
            if study_hours_per_day is not None:
                updates.append("study_hours_per_day = ?")
                values.append(study_hours_per_day)
            if learning_style is not None:
                updates.append("learning_style = ?")
                values.append(learning_style)
            if exam_dates is not None:
                updates.append("exam_dates_json = ?")
                values.append(json.dumps(exam_dates))
            if updates:
                values.append(user_id)
                await db.execute(
                    f"UPDATE user_preferences SET {', '.join(updates)} WHERE user_id = ?",
                    values,
                )
        else:
            await db.execute(
                """INSERT INTO user_preferences
                   (user_id, weak_subjects_json, study_hours_per_day, learning_style, exam_dates_json)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    user_id,
                    json.dumps(weak_subjects or []),
                    study_hours_per_day or 3,
                    learning_style or "visual",
                    json.dumps(exam_dates or {}),
                ),
            )


async def get_user_preferences(user_id: int) -> Optional[Dict[str, Any]]:
    """Return user preferences dict or None."""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM user_preferences WHERE user_id = ?", (user_id,)
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        data = dict(row)
        data["weak_subjects"] = json.loads(data["weak_subjects_json"])
        data["exam_dates"] = json.loads(data["exam_dates_json"])
        return data


async def delete_user_preferences(user_id: int) -> None:
    """Delete user preferences by user_id."""
    async with get_db() as db:
        await db.execute("DELETE FROM user_preferences WHERE user_id = ?", (user_id,))
