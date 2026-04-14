from __future__ import annotations


def build_weekly_report_prompt(data_context: str) -> str:
    return f"""You are an executive performance coach.
Generate a detailed, professional weekly performance report for this employee.

{data_context}

Return VALID JSON only with this exact structure:
{{
  "performance_rating": "Outstanding/Excellent/Good/Fair/Needs Improvement",
  "summary": "2-3 sentence executive summary of the week's overall performance",
  "highlights": ["3 specific achievements or positive patterns this week"],
  "focus_areas": ["3 specific areas to improve or areas showing concern"],
  "coaching_tips": ["3 actionable, specific coaching recommendations for next week"],
  "action_items": ["3 concrete actions to take in the coming week"],
  "motivational_message": "A brief, personalized motivational message"
}}

Be specific, data-driven, and constructive. Focus on actionable insights."""

