"""
IB AI Agent System — IB Core Handlers

Handlers for Theory of Knowledge (TOK), CAS, and Extended Essay (EE).
"""

from __future__ import annotations

import json
from typing import List, Optional

from ai_engine import ai_engine
from database import (
    get_cas_strand_totals,
    insert_cas_activity,
    insert_conversation,
)
from prompts.system_prompts import (
    CAS_PROJECTS,
    CAS_REFLECTION,
    EE_RQ_REFINE,
    EE_STRUCTURE,
    TOK_ESSAY,
    TOK_EXHIBITION,
    TOK_KQ,
)


class TOKHandler:
    """IB Theory of Knowledge handler — KQs, essay planning, exhibition."""

    async def knowledge_question(self, rls: str, user_id: int) -> str:
        """Parse a real-life situation into 3 knowledge questions mapped to AOK + WOK."""
        prompt = TOK_KQ.format(rls=rls)
        response = await ai_engine.generate(prompt)

        await insert_conversation(
            user_id=user_id,
            command="/tok",
            message=rls,
            response=response,
        )
        return response

    async def essay_plan(self, prescribed_title: str, user_id: int) -> str:
        """Generate a TOK essay plan with 2 claims + 2 counterclaims."""
        prompt = TOK_ESSAY.format(prescribed_title=prescribed_title)
        response = await ai_engine.generate(prompt)

        await insert_conversation(
            user_id=user_id,
            command="/tok_essay",
            message=prescribed_title,
            response=response,
        )
        return response

    async def exhibition_link(
        self, prompt_number: str, object_description: str, user_id: int
    ) -> str:
        """Connect an object to a TOK exhibition prompt with 3 justification points."""
        prompt = TOK_EXHIBITION.format(
            prompt_number=prompt_number,
            object_description=object_description,
        )
        response = await ai_engine.generate(prompt)

        await insert_conversation(
            user_id=user_id,
            command="/tok_exhibition",
            message=f"Prompt {prompt_number}: {object_description[:100]}",
            response=response,
        )
        return response


class CASHandler:
    """IB CAS handler — project ideas, reflection prompts, activity logging."""

    REFLECTION_STAGE_QUESTIONS = {
        "planning": (
            "1. What do you hope to achieve through this activity, and why does it matter to you?\n"
            "2. What challenges do you anticipate, and how will you address them?\n"
            "3. How does this activity connect to at least one of the 7 CAS learning outcomes?\n"
            "4. What skills or knowledge do you need to develop before starting?\n"
            "5. How will you know if this activity has been successful?"
        ),
        "action": (
            "1. What have you learned about yourself during this activity so far?\n"
            "2. How have you demonstrated commitment and perseverance?\n"
            "3. What unexpected challenges arose, and how did you adapt?\n"
            "4. How has this activity changed your understanding of the issue/community?\n"
            "5. What evidence are you collecting to document your experience?"
        ),
        "reflection": (
            "1. How has this activity contributed to your personal growth?\n"
            "2. What would you do differently if you could start over?\n"
            "3. How did this activity develop your understanding of global issues?\n"
            "4. What CAS learning outcomes did you meet, and how?\n"
            "5. How might you continue this work or apply what you learned in the future?"
        ),
    }

    async def project_ideas(
        self, hours: float, interests: str, user_id: int
    ) -> str:
        """Suggest at least 2 ideas per CAS strand mapped to IB learning outcomes."""
        prompt = CAS_PROJECTS.format(hours=hours, interests=interests)
        response = await ai_engine.generate(prompt)

        await insert_conversation(
            user_id=user_id,
            command="/cas",
            message=f"Hours: {hours}, Interests: {interests}",
            response=response,
        )
        return response

    async def reflection_prompt(
        self, activity: str, stage: str, user_id: int
    ) -> str:
        """Generate 5 IB-language reflection questions for a given stage."""
        stage_key = stage.lower().strip()
        questions = self.REFLECTION_STAGE_QUESTIONS.get(
            stage_key, self.REFLECTION_STAGE_QUESTIONS["reflection"]
        )
        prompt = CAS_REFLECTION.format(
            activity=activity,
            stage=stage,
            stage_questions=questions,
        )
        response = await ai_engine.generate(prompt)

        await insert_conversation(
            user_id=user_id,
            command="/cas_reflect",
            message=f"[{stage}] {activity}",
            response=response,
        )
        return response

    async def log_activity(
        self,
        user_id: int,
        activity_name: str,
        strand: str,
        hours: float,
        reflection: str,
        evidence_links: Optional[List[str]] = None,
    ) -> str:
        """Save a CAS activity to the database and return strand totals."""
        if strand.upper() not in ("C", "A", "S"):
            return "❌ Invalid strand. Use C (Creativity), A (Activity), or S (Service)."

        await insert_cas_activity(
            user_id=user_id,
            activity_name=activity_name,
            strand=strand.upper(),
            hours=hours,
            reflection=reflection,
            evidence_links=evidence_links or [],
        )

        totals = await get_cas_strand_totals(user_id)
        c_total = totals.get("C", 0)
        a_total = totals.get("A", 0)
        s_total = totals.get("S", 0)
        grand_total = c_total + a_total + s_total

        return (
            f"✅ Logged: {activity_name} ({strand.upper()}) — {hours}h\n\n"
            f"📊 CAS Totals:\n"
            f"   🎨 Creativity: {c_total:.1f}h\n"
            f"   🏃 Activity: {a_total:.1f}h\n"
            f"   🤝 Service: {s_total:.1f}h\n"
            f"   ─────────────\n"
            f"   📋 Total: {grand_total:.1f}h"
        )


class EEHandler:
    """IB Extended Essay handler — RQ refinement, structure review, source guidance."""

    async def rq_refine(self, subject: str, broad_topic: str, user_id: int) -> str:
        """Generate 3 focused research questions with scope and methodology notes."""
        prompt = EE_RQ_REFINE.format(subject=subject, broad_topic=broad_topic)
        response = await ai_engine.generate(prompt)

        await insert_conversation(
            user_id=user_id,
            command="/ee",
            message=f"[{subject}] {broad_topic}",
            response=response,
        )
        return response

    async def structure_review(
        self, outline: str, subject: str, user_id: int
    ) -> str:
        """Review an EE outline with chapter feedback and word count allocation."""
        prompt = EE_STRUCTURE.format(outline=outline, subject=subject)
        response = await ai_engine.generate(prompt)

        await insert_conversation(
            user_id=user_id,
            command="/ee_review",
            message=f"[{subject}] {outline[:200]}",
            response=response,
        )
        return response

    async def source_types(self, subject: str, rq: str, user_id: int) -> str:
        """Recommend primary vs secondary sources and suggest databases."""
        prompt = (
            f"You are an IB Extended Essay supervisor. For this research question in {subject}:\n\n"
            f"\"{rq}\"\n\n"
            f"Provide:\n"
            f"1. **Primary sources** — what counts as primary for {subject}? List 3-5 specific types.\n"
            f"2. **Secondary sources** — what counts as secondary? List 3-5 types.\n"
            f"3. **Search strategy** — specific search terms, Boolean operators, filters.\n"
            f"4. **3 suggested databases** — real academic databases appropriate for {subject}.\n"
            f"5. **Source evaluation criteria** — how to assess reliability for EE purposes.\n"
            f"6. **Common mistakes** — 3 errors students make with sources in {subject} EEs."
        )
        response = await ai_engine.generate(prompt)

        await insert_conversation(
            user_id=user_id,
            command="/ee_sources",
            message=f"[{subject}] {rq[:150]}",
            response=response,
        )
        return response
