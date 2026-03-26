"""
IB AI Agent System — Handlers Package

Contains all Telegram command handlers organized by domain.
"""

from handlers.ib_subjects import (
    BusinessHandler,
    EconHandler,
    ESSHandler,
    EnglishHandler,
    MathHandler,
    SpanishHandler,
)
from handlers.ib_core import CASHandler, EEHandler, TOKHandler
from handlers.business_tools import ContentGenerator, IdeaValidator, RevenueTracker
from handlers.study_planner import StudyPlanner

__all__ = [
    "MathHandler",
    "BusinessHandler",
    "EconHandler",
    "ESSHandler",
    "SpanishHandler",
    "EnglishHandler",
    "TOKHandler",
    "CASHandler",
    "EEHandler",
    "IdeaValidator",
    "RevenueTracker",
    "ContentGenerator",
    "StudyPlanner",
]
