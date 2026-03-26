"""
IB AI Agent System — Business Tools

Idea validator, revenue tracker, and content generator for student entrepreneurs.
"""

from __future__ import annotations

from typing import Optional

from ai_engine import ai_engine
from database import (
    get_business_projects_by_user,
    insert_business_project,
    insert_conversation,
    update_business_project,
)
from prompts.system_prompts import BUSINESS_VALIDATOR


class IdeaValidator:
    """Validate business ideas with viability scoring, market sizing, and risk analysis."""

    async def validate(
        self, idea: str, industry: str, user_id: int
    ) -> str:
        """Produce a full validation report: score, TAM/SAM/SOM, monetization, MVP, risks."""
        prompt = BUSINESS_VALIDATOR.format(idea=idea, industry=industry)
        response = await ai_engine.generate(prompt)

        await insert_conversation(
            user_id=user_id,
            command="/validate",
            message=f"{idea} [{industry}]",
            response=response,
        )
        return response


class RevenueTracker:
    """Track business project revenue, expenses, and generate P&L summaries."""

    async def log_transaction(
        self,
        user_id: int,
        project_name: str,
        amount: float,
        transaction_type: str,
    ) -> str:
        """
        Log a revenue or expense transaction.
        Creates the project if it does not exist, otherwise updates totals.
        """
        if transaction_type not in ("revenue", "expense"):
            return "❌ Transaction type must be 'revenue' or 'expense'."

        projects = await get_business_projects_by_user(user_id)
        project = next(
            (p for p in projects if p["name"].lower() == project_name.lower()),
            None,
        )

        if project is None:
            if transaction_type == "revenue":
                await insert_business_project(
                    user_id=user_id,
                    name=project_name,
                    revenue_total=amount,
                    expenses_total=0,
                )
            else:
                await insert_business_project(
                    user_id=user_id,
                    name=project_name,
                    revenue_total=0,
                    expenses_total=amount,
                )
            projects = await get_business_projects_by_user(user_id)
            project = next(
                (p for p in projects if p["name"].lower() == project_name.lower()),
                None,
            )
        else:
            if transaction_type == "revenue":
                new_rev = project["revenue_total"] + amount
                await update_business_project(
                    project["id"], revenue_total=new_rev
                )
                project["revenue_total"] = new_rev
            else:
                new_exp = project["expenses_total"] + amount
                await update_business_project(
                    project["id"], expenses_total=new_exp
                )
                project["expenses_total"] = new_exp

        revenue = project["revenue_total"]
        expenses = project["expenses_total"]
        profit = revenue - expenses
        margin = (profit / revenue * 100) if revenue > 0 else 0

        return (
            f"✅ Logged {transaction_type}: ${amount:,.2f}\n\n"
            f"📊 {project_name} — P&L Summary:\n"
            f"   💰 Revenue: ${revenue:,.2f}\n"
            f"   💸 Expenses: ${expenses:,.2f}\n"
            f"   {'📈' if profit >= 0 else '📉'} Profit: ${profit:,.2f}\n"
            f"   📊 Margin: {margin:.1f}%"
        )

    async def get_pl_summary(self, user_id: int, project_name: str) -> str:
        """Generate a formatted P&L summary for a project."""
        projects = await get_business_projects_by_user(user_id)
        project = next(
            (p for p in projects if p["name"].lower() == project_name.lower()),
            None,
        )

        if project is None:
            return f"❌ Project '{project_name}' not found. Log a transaction first with /log."

        revenue = project["revenue_total"]
        expenses = project["expenses_total"]
        gross_profit = revenue - expenses
        net_profit = gross_profit
        gross_margin = (gross_profit / revenue * 100) if revenue > 0 else 0
        net_margin = (net_profit / revenue * 100) if revenue > 0 else 0

        return (
            f"📋 **{project['name']}** — Income Statement\n"
            f"{'─' * 35}\n"
            f"Revenue ............. ${revenue:>12,.2f}\n"
            f"(-) Expenses ........ ${expenses:>12,.2f}\n"
            f"{'─' * 35}\n"
            f"Gross Profit ........ ${gross_profit:>12,.2f}\n"
            f"{'─' * 35}\n"
            f"Net Profit .......... ${net_profit:>12,.2f}\n\n"
            f"📊 Ratios:\n"
            f"   Gross Margin: {gross_margin:.1f}%\n"
            f"   Net Margin: {net_margin:.1f}%\n\n"
            f"Stage: {project['stage']}\n"
            f"Updated: {project['updated_at']}"
        )

    @staticmethod
    def pricing_calculator(
        cost: float,
        desired_margin: float,
        competitor_price: Optional[float] = None,
    ) -> str:
        """
        Calculate cost-plus and value-based pricing.
        Returns recommendation with positioning advice.
        """
        cost_plus_price = cost / (1 - desired_margin / 100)

        lines = [
            "💰 Pricing Analysis",
            f"{'─' * 35}",
            f"Unit Cost: ${cost:,.2f}",
            f"Desired Margin: {desired_margin:.0f}%",
            "",
            "📌 Cost-Plus Pricing:",
            f"   Price = ${cost_plus_price:,.2f}",
            f"   Profit per unit = ${cost_plus_price - cost:,.2f}",
        ]

        if competitor_price is not None:
            diff = ((cost_plus_price - competitor_price) / competitor_price) * 100
            lines.extend([
                "",
                "📌 Competitive Positioning:",
                f"   Competitor price: ${competitor_price:,.2f}",
                f"   Your cost-plus: ${cost_plus_price:,.2f}",
                f"   Difference: {diff:+.1f}%",
            ])
            if diff > 10:
                lines.append(
                    "   ⚠️ You are >10% above market. Consider:\n"
                    "      → Adding premium features to justify\n"
                    "      → Reducing costs\n"
                    "      → Targeting a niche segment"
                )
            elif diff < -10:
                lines.append(
                    "   💡 You are significantly below market. Consider:\n"
                    "      → Raising price to capture more value\n"
                    "      → Positioning as 'quality + value'"
                )
            else:
                lines.append("   ✅ Competitive range. Focus on differentiation.")

        lines.extend([
            "",
            "📌 Recommendation:",
            f"   Start at ${cost_plus_price:,.2f} (cost-plus)",
        ])
        if competitor_price is not None:
            avg = (cost_plus_price + competitor_price) / 2
            lines.append(f"   Adjust toward ${avg:,.2f} based on market feedback")

        return "\n".join(lines)


class ContentGenerator:
    """Generate social media calendars and pitch deck outlines."""

    async def social_calendar(
        self,
        niche: str,
        platforms: str,
        weeks: int,
        user_id: int,
    ) -> str:
        """Generate a week-by-week social media content plan."""
        prompt = (
            f"You are a social media strategist. Create a {weeks}-week content calendar for:\n\n"
            f"Niche: {niche}\n"
            f"Platforms: {platforms}\n\n"
            f"Requirements:\n"
            f"- Minimum 3 posts per week per platform\n"
            f"- Each post: caption, hashtags (5-10), best posting time\n"
            f"- Platform-native format (Instagram: carousel/reel idea, Twitter: thread, TikTok: hook)\n"
            f"- Mix: 40% educational, 30% engagement, 20% promotional, 10% behind-the-scenes\n"
            f"- Include content pillars (3-4 themes to rotate)\n\n"
            f"Format as: Week X → Day → Platform → Post type → Caption draft → Hashtags"
        )
        response = await ai_engine.generate(prompt)

        await insert_conversation(
            user_id=user_id,
            command="/calendar",
            message=f"{niche} on {platforms} ({weeks}w)",
            response=response,
        )
        return response

    async def pitch_deck_outline(
        self, idea: str, audience: str, user_id: int
    ) -> str:
        """Generate a 10-slide pitch deck outline with content notes."""
        prompt = (
            f"You are a startup advisor. Create a 10-slide pitch deck outline for:\n\n"
            f"Idea: {idea}\n"
            f"Target audience: {audience}\n\n"
            f"For each slide provide:\n"
            f"1. Slide title\n"
            f"2. Key content points (bullet points)\n"
            f"3. Suggested data/visuals to include\n"
            f"4. Speaker notes (what to say, 2-3 sentences)\n\n"
            f"Slides: Title, Problem, Solution, Market Size, Business Model, "
            f"Traction, Competition, Team, Financials, Ask"
        )
        response = await ai_engine.generate(prompt)

        await insert_conversation(
            user_id=user_id,
            command="/pitch",
            message=f"{idea} for {audience}",
            response=response,
        )
        return response
