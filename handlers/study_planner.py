"""
IB AI Agent System — Study Planner

SM-2 spaced repetition, exam scheduling, and personalized study plans.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Dict, List, Optional

from ai_engine import ai_engine
from database import (
    get_due_cards,
    get_study_cards_by_user,
    get_user_preferences,
    insert_conversation,
    insert_study_card,
    update_study_card,
)
from prompts.system_prompts import STUDY_PLANNER


class StudyPlanner:
    """IB study planner with SM-2 spaced repetition, flashcards, and exam countdown."""

    SM2_INITIAL_INTERVAL: float = 1.0
    SM2_INITIAL_EASE: float = 2.5

    async def generate_schedule(
        self,
        user_id: int,
        days_until_exam: int,
        weak_subjects: Optional[List[str]] = None,
        study_hours_per_day: float = 3,
    ) -> str:
        """Generate a day-by-day study schedule with spaced repetition."""
        weak = weak_subjects or []
        weak_str = ", ".join(weak) if weak else "None specified"
        prompt = STUDY_PLANNER.format(
            days_until_exam=days_until_exam,
            weak_subjects=weak_str,
            study_hours_per_day=study_hours_per_day,
        )
        response = await ai_engine.generate(prompt)

        await insert_conversation(
            user_id=user_id,
            command="/schedule",
            message=f"{days_until_exam} days, weak: {weak_str}",
            response=response,
        )
        return response

    async def create_flashcard(
        self, subject: str, concept: str, user_id: int
    ) -> str:
        """Create an IB-aligned flashcard with SM-2 defaults and save to DB."""
        prompt = (
            f"You are an IB tutor. Create a flashcard for:\n"
            f"Subject: {subject}\n"
            f"Concept: {concept}\n\n"
            f"Provide:\n"
            f"- **Front**: A clear question or prompt (testable, IB-syllabus aligned)\n"
            f"- **Back**: A concise answer with key points (suitable for quick review)\n\n"
            f"Format:\n"
            f"FRONT: [question]\n"
            f"BACK: [answer]"
        )
        response = await ai_engine.generate(prompt)

        front = concept
        back = response
        for line in response.split("\n"):
            if line.strip().upper().startswith("FRONT:"):
                front = line.split(":", 1)[1].strip()
            elif line.strip().upper().startswith("BACK:"):
                back = line.split(":", 1)[1].strip()

        card_id = await insert_study_card(
            user_id=user_id,
            subject=subject,
            topic=concept,
            front=front,
            back=back,
            interval_days=self.SM2_INITIAL_INTERVAL,
            repetitions=0,
            ease_factor=self.SM2_INITIAL_EASE,
        )

        return (
            f"✅ Flashcard created (ID: {card_id})\n\n"
            f"📚 Subject: {subject}\n"
            f"📝 Topic: {concept}\n\n"
            f"**Front:** {front}\n\n"
            f"**Back:** {back}\n\n"
            f"⏰ Next review: Tomorrow (SM-2 interval: {self.SM2_INITIAL_INTERVAL:.0f} day)"
        )

    async def review_due(self, user_id: int) -> str:
        """List all flashcards due for review today."""
        cards = await get_due_cards(user_id)
        if not cards:
            return (
                "✅ No cards due for review today!\n\n"
                "Use `/flashcard <subject> <concept>` to create new flashcards."
            )

        lines = ["📚 **Cards Due for Review**\n"]
        for i, card in enumerate(cards, 1):
            emoji = {"Math": "🔢", "Business": "💼", "Economics": "📊",
                     "ESS": "🌍", "Spanish": "🇪🇸", "English": "📝"}.get(
                card["subject"], "📖"
            )
            lines.append(
                f"{i}. {emoji} **{card['subject']}** — {card['topic']}\n"
                f"   Front: {card['front'][:80]}{'...' if len(card['front']) > 80 else ''}\n"
                f"   Due since: {card['due_date']} | Reps: {card['repetitions']}\n"
            )

        lines.append(
            "\n💡 Use `/review <card_id> <quality 0-5>` to mark a card as reviewed."
        )
        return "\n".join(lines)

    async def update_card_review(
        self, user_id: int, card_id: int, quality: int
    ) -> str:
        """
        Update a flashcard after review using SM-2 algorithm.
        quality: 0-5 (0-2 = fail, 3 = hard, 4 = good, 5 = easy)
        """
        if quality < 0 or quality > 5:
            return "❌ Quality must be 0–5. (0-2: fail, 3: hard, 4: good, 5: easy)"

        cards = await get_study_cards_by_user(user_id)
        card = next((c for c in cards if c["id"] == card_id), None)
        if card is None:
            return f"❌ Card ID {card_id} not found."

        # SM-2 algorithm
        old_ease = card["ease_factor"]
        old_reps = card["repetitions"]
        old_interval = card["interval_days"]

        new_ease = max(1.3, old_ease + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)))

        if quality < 3:
            new_reps = 0
            new_interval = 1.0
        else:
            new_reps = old_reps + 1
            if new_reps == 1:
                new_interval = 1.0
            elif new_reps == 2:
                new_interval = 6.0
            else:
                new_interval = old_interval * new_ease

        new_due = (date.today() + timedelta(days=int(new_interval))).isoformat()

        await update_study_card(
            card_id,
            repetitions=new_reps,
            ease_factor=round(new_ease, 2),
            interval_days=round(new_interval, 1),
            due_date=new_due,
        )

        quality_label = {0: "Again", 1: "Again", 2: "Hard (fail)",
                         3: "Hard", 4: "Good", 5: "Easy"}.get(quality, "Unknown")

        return (
            f"✅ Card {card_id} reviewed — **{quality_label}**\n\n"
            f"📚 {card['subject']} — {card['topic']}\n"
            f"📊 SM-2 Update:\n"
            f"   Ease: {old_ease:.2f} → {new_ease:.2f}\n"
            f"   Reps: {old_reps} → {new_reps}\n"
            f"   Interval: {old_interval:.1f}d → {new_interval:.1f}d\n"
            f"   ⏰ Next review: {new_due}"
        )

    async def exam_countdown(self, user_id: int) -> str:
        """Show days remaining per subject with urgency indicators."""
        prefs = await get_user_preferences(user_id)
        if prefs is None or not prefs.get("exam_dates"):
            return (
                "❌ No exam dates set. Use `/exams <subject>=<YYYY-MM-DD>` to set them.\n"
                "Example: `/exams Math=2025-05-15 Business=2025-05-20`"
            )

        today = date.today()
        lines = ["📅 **Exam Countdown**\n"]
        sorted_exams = sorted(
            prefs["exam_dates"].items(),
            key=lambda x: x[1],
        )

        for subject, date_str in sorted_exams:
            exam_date = date.fromisoformat(date_str)
            days_left = (exam_date - today).days

            if days_left < 0:
                label = "✅ Done"
                emoji = "✅"
            elif days_left < 14:
                label = f"{days_left} days — URGENT"
                emoji = "🔴"
            elif days_left <= 30:
                label = f"{days_left} days — Soon"
                emoji = "🟡"
            else:
                label = f"{days_left} days"
                emoji = "🟢"

            lines.append(f"{emoji} **{subject}**: {label} (exam: {date_str})")

        lines.append("\n🔴 <14 days | 🟡 14–30 days | 🟢 30+ days")
        return "\n".join(lines)
