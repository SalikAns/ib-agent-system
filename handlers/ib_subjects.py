"""
IB AI Agent System — IB Subject Handlers

Handlers for Math AA HL, Business HL, Economics HL, ESS SL, Spanish AB SL, and English SL.
"""

from __future__ import annotations

import re
from typing import Optional

from ai_engine import ai_engine
from database import insert_conversation
from prompts.system_prompts import (
    BUSINESS_CASE_STUDY,
    BUSINESS_CUEGIS,
    BUSINESS_ESSAY,
    BUSINESS_RATIO_ANALYSIS,
    ESS_CASE_STUDY,
    ESS_CONCEPT,
    ECON_DIAGRAM,
    ECON_IA_SECTION,
    ECON_POLICY_EVAL,
    ENGLISH_IOP,
    ENGLISH_PAPER1,
    MATH_GRAPH_ANALYSIS,
    MATH_MARK_SCHEME,
    MATH_SOLVER,
    SPANISH_GRAMMAR,
    SPANISH_WRITING,
)


class MathHandler:
    """IB Math AA HL handler — solve, mark scheme, and graph analysis."""

    TOPIC_KEYWORDS = {
        "calculus": [
            "derivative", "integral", "differentiate", "integrate",
            "differentiation", "integration", "dy/dx", "antiderivative",
            "chain rule", "product rule", "quotient rule", "area under",
            "rate of change", "tangent line", "critical point",
        ],
        "vectors": [
            "vector", "dot product", "cross product", "scalar",
            "magnitude", "direction", "parallel", "perpendicular",
            "projection", "plane", "line in 3d",
        ],
        "statistics": [
            "mean", "variance", "standard deviation", "probability",
            "distribution", "normal", "binomial", "poisson",
            "hypothesis test", "confidence interval", "regression",
            "correlation", "chi-squared", "z-score",
        ],
        "algebra": [
            "matrix", "determinant", "eigenvalue", "inverse",
            "system of equations", "gaussian", "polynomial",
            "roots", "factor", "quadratic", "logarithm", "exponential",
            "sequence", "series", "induction",
        ],
    }

    def _detect_topic(self, problem: str) -> str:
        """Detect the IB Math topic from keywords in the problem text."""
        lower = problem.lower()
        scores: dict[str, int] = {}
        for topic, keywords in self.TOPIC_KEYWORDS.items():
            scores[topic] = sum(1 for kw in keywords if kw in lower)
        best = max(scores, key=scores.get)
        if scores[best] == 0:
            return "general"
        return best

    async def solve(self, problem: str, user_id: int) -> str:
        """Detect topic, select prompt, call AI engine, verify boxed answer."""
        topic = self._detect_topic(problem)
        prompt = MATH_SOLVER.format(problem=problem, topic=topic)
        response = await ai_engine.generate(prompt)

        if "\\boxed" not in response:
            response += "\n\n⚠️ Note: No \\boxed{{}} answer detected — please verify the final answer manually."

        await insert_conversation(
            user_id=user_id,
            command="/math",
            message=problem,
            response=response,
        )
        return response

    async def mark_scheme(self, question: str, user_id: int) -> str:
        """Generate an IB-style mark scheme with M, A, R marks."""
        prompt = MATH_MARK_SCHEME.format(question=question)
        response = await ai_engine.generate(prompt)

        await insert_conversation(
            user_id=user_id,
            command="/markscheme",
            message=question,
            response=response,
        )
        return response

    async def graph_description(self, function_str: str, user_id: int) -> str:
        """Provide full graph analysis: domain, range, intercepts, asymptotes, turning points."""
        prompt = MATH_GRAPH_ANALYSIS.format(function_str=function_str)
        response = await ai_engine.generate(prompt)

        await insert_conversation(
            user_id=user_id,
            command="/graph",
            message=function_str,
            response=response,
        )
        return response


class BusinessHandler:
    """IB Business Management HL handler — essays, case studies, ratios, CUEGIS."""

    async def essay_structure(
        self, question: str, user_id: int, marks: int = 20
    ) -> str:
        """Generate a structured essay plan with per-section mark allocations."""
        total_body = marks - 4
        body_marks = total_body // 3
        remainder = total_body % 3
        prompt = BUSINESS_ESSAY.format(
            question=question,
            marks=marks,
            intro_marks=2,
            body1_marks=body_marks + (1 if remainder >= 1 else 0),
            body2_marks=body_marks + (1 if remainder >= 2 else 0),
            body3_marks=body_marks,
            concl_marks=2,
        )
        response = await ai_engine.generate(prompt)

        await insert_conversation(
            user_id=user_id,
            command="/essay",
            message=question,
            response=response,
        )
        return response

    async def case_analysis(self, case_text: str, user_id: int) -> str:
        """Produce SWOT + PEST tables and stakeholder analysis."""
        prompt = BUSINESS_CASE_STUDY.format(case_text=case_text)
        response = await ai_engine.generate(prompt)

        await insert_conversation(
            user_id=user_id,
            command="/case",
            message=case_text[:200],
            response=response,
        )
        return response

    async def ratio_analysis(
        self,
        revenue: float,
        costs: float,
        assets: float,
        liabilities: float,
        user_id: int,
    ) -> str:
        """Calculate and interpret 6 key financial ratios."""
        prompt = BUSINESS_RATIO_ANALYSIS.format(
            revenue=revenue,
            costs=costs,
            assets=assets,
            liabilities=liabilities,
        )
        response = await ai_engine.generate(prompt)

        await insert_conversation(
            user_id=user_id,
            command="/ratios",
            message=f"Rev={revenue} Cost={costs} Assets={assets} Liab={liabilities}",
            response=response,
        )
        return response

    async def cuegis_examples(
        self, concept: str, industry: str, user_id: int
    ) -> str:
        """Provide 3 real-world CUEGIS examples post-2018."""
        prompt = BUSINESS_CUEGIS.format(concept=concept, industry=industry)
        response = await ai_engine.generate(prompt)

        await insert_conversation(
            user_id=user_id,
            command="/cuegis",
            message=f"{concept} in {industry}",
            response=response,
        )
        return response


class EconHandler:
    """IB Economics HL handler — diagrams, IA commentary, policy evaluation."""

    async def diagram_explain(
        self, diagram_type: str, scenario: str, user_id: int
    ) -> str:
        """Generate ASCII diagram with axes, shifts, and 4-step chain of reasoning."""
        prompt = ECON_DIAGRAM.format(
            diagram_type=diagram_type, scenario=scenario
        )
        response = await ai_engine.generate(prompt)

        await insert_conversation(
            user_id=user_id,
            command="/econ",
            message=f"{diagram_type}: {scenario}",
            response=response,
        )
        return response

    async def ia_section(
        self, section: str, article_summary: str, user_id: int
    ) -> str:
        """Guide the student through an IA section: introduction, body, or conclusion."""
        section_instructions = {
            "introduction": (
                "Write an introduction that: hooks with a real-world economic fact, "
                "states the economic concept from the IB syllabus, and links clearly to the article. "
                "Keep under 150 words."
            ),
            "body": (
                "Write the body analysis that: defines the key economic terms from the IB syllabus, "
                "explains the relevant economic theory, applies the theory to the article with specific "
                "data points, and includes a description of a labelled diagram. Keep under 500 words."
            ),
            "conclusion": (
                "Write a conclusion that: evaluates the policy/economic action from multiple stakeholder "
                "perspectives, considers short-run vs long-run impacts, acknowledges limitations/assumptions, "
                "and suggests policy implications. Keep under 200 words."
            ),
        }
        instruction = section_instructions.get(
            section, section_instructions["body"]
        )
        prompt = ECON_IA_SECTION.format(
            section=section,
            article_summary=article_summary,
            section_instruction=instruction,
        )
        response = await ai_engine.generate(prompt)

        await insert_conversation(
            user_id=user_id,
            command="/ia",
            message=f"[{section}] {article_summary[:150]}",
            response=response,
        )
        return response

    async def policy_evaluate(
        self, policy: str, context: str, user_id: int
    ) -> str:
        """Evaluate a policy across effectiveness, equity, sustainability, and implementation."""
        prompt = ECON_POLICY_EVAL.format(policy=policy, context=context)
        response = await ai_engine.generate(prompt)

        await insert_conversation(
            user_id=user_id,
            command="/policy",
            message=policy,
            response=response,
        )
        return response


class ESSHandler:
    """IB Environmental Systems and Societies SL handler."""

    async def concept_explain(self, concept: str, user_id: int) -> str:
        """Explain an ESS concept with systems thinking framework."""
        prompt = ESS_CONCEPT.format(concept=concept)
        response = await ai_engine.generate(prompt)

        await insert_conversation(
            user_id=user_id,
            command="/ess",
            message=concept,
            response=response,
        )
        return response

    async def case_study(
        self, environment: str, issue: str, user_id: int
    ) -> str:
        """Provide one local + one global case study with data points."""
        prompt = ESS_CASE_STUDY.format(environment=environment, issue=issue)
        response = await ai_engine.generate(prompt)

        await insert_conversation(
            user_id=user_id,
            command="/ess_case",
            message=f"{environment}: {issue}",
            response=response,
        )
        return response


class SpanishHandler:
    """IB Spanish AB Initio SL handler — grammar check and writing scaffold."""

    async def grammar_check(
        self, text: str, user_id: int, level: str = "ab_initio"
    ) -> str:
        """Check Spanish text with corrections and English explanations."""
        prompt = SPANISH_GRAMMAR.format(text=text, level=level)
        response = await ai_engine.generate(prompt)

        await insert_conversation(
            user_id=user_id,
            command="/spanish",
            message=text[:200],
            response=response,
        )
        return response

    async def writing_scaffold(
        self, task_type: str, topic: str, user_id: int
    ) -> str:
        """Create a writing scaffold with structure, vocab, and linking phrases."""
        prompt = SPANISH_WRITING.format(task_type=task_type, topic=topic)
        response = await ai_engine.generate(prompt)

        await insert_conversation(
            user_id=user_id,
            command="/spanish_write",
            message=f"{task_type}: {topic}",
            response=response,
        )
        return response


class EnglishHandler:
    """IB English Language and Literature SL handler — Paper 1 and Individual Oral."""

    async def paper1_analysis(
        self, text_type: str, extract: str, user_id: int
    ) -> str:
        """Provide guiding questions for Paper 1 text analysis."""
        prompt = ENGLISH_PAPER1.format(text_type=text_type, extract=extract)
        response = await ai_engine.generate(prompt)

        await insert_conversation(
            user_id=user_id,
            command="/english",
            message=f"[{text_type}] {extract[:150]}",
            response=response,
        )
        return response

    async def iop_outline(self, text: str, focus: str, user_id: int) -> str:
        """Generate Individual Oral commentary outline with key moments."""
        prompt = ENGLISH_IOP.format(text=text, focus=focus)
        response = await ai_engine.generate(prompt)

        await insert_conversation(
            user_id=user_id,
            command="/iop",
            message=f"{focus}: {text[:150]}",
            response=response,
        )
        return response
