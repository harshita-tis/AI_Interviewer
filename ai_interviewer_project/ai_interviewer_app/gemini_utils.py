from google import genai
from django.conf import settings
import json,re

client=genai.Client(api_key=settings.GEMINI_API_KEY)

MODEL_NAME = "gemma-3-27b-it" 


def generate_questions(role, experience, skills, candidate_name):

    prompt = f"""
You are a strict and professional senior technical interviewer.

Generate EXACTLY 2 interview questions for the following candidate:

Candidate Name: {candidate_name}
Role: {role}
Experience Level: {experience}
Skills: {skills}

Rules:
- First question must ask the candidate to introduce themselves.
- Questions must match the experience level.
- Gradually increase difficulty.
- Mix theory and practical backend scenarios.
- Keep each question short and conversational.
- Suitable for voice-based interview.
- Do NOT include explanations.
- Do NOT include any introduction text.
- Output ONLY numbered questions (1 to 12).
- If you include extra text, the answer is invalid.

Format strictly like this:
1. Question
2. Question
...
12. Question
"""

    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt,
        config={
            "max_output_tokens": 500,
            "temperature": 0.3
        }
    )

    text = response.text.strip()

    questions = []
    for line in text.split("\n"):
        line = line.strip()
        if line and line[0].isdigit():
            question = line.split(".", 1)[-1].strip()
            questions.append(question)

    return questions



def evaluate_answer(question, answer, role=None, skills=None):
    prompt = f"""
    You are a senior technical interviewer evaluating a candidate’s response.

    Interview Question:
    {question}

    Candidate Answer:
    {answer}

    Context: Role={role or 'General'}, Skills={skills if isinstance(skills, list) else (skills or '')}. Use skill_breakdown keys relevant to this role.

    Evaluate the answer realistically based on:
    - Technical depth
    - Practical understanding
    - Clarity of communication
    - Confidence and structure

    Provide STRICT JSON output only in this format:

    {{
      "technical_score": 0-100,
      "communication_score": 0-100,
      "skill_breakdown": {{ "Skill1": 0-100, "Skill2": 0-100, ... }} (use 4-6 skills relevant to role)
      }}
    Return ONLY valid JSON.
    """

    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt
    )

    cleaned = response.text.strip()
    
    # Extract JSON from any surrounding text
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group())
            ts, cs = data.get("technical_score", 0), data.get("communication_score", 0)
            if 0 < ts <= 10:
                data["technical_score"] = ts * 10
            if 0 < cs <= 10:
                data["communication_score"] = cs * 10
            return data
        except json.JSONDecodeError:
            pass
    return {"technical_score": 0, "communication_score": 0, "skill_breakdown": {}}


def generate_scorecard_content(role, skills, name, technical_avg, communication_avg,
                               skill_breakdown, qna_summary):
    """AI-generated communication_review, recommendation, skill_wise_reviews."""
    skills_str = ", ".join(str(s) for s in skills) if isinstance(skills, list) else (skills or "N/A")
    skill_scores_str = ", ".join([f"{k}: {v}%" for k, v in (skill_breakdown or {}).items()]) or "N/A"
    skill_keys = list(skill_breakdown.keys()) if skill_breakdown else []
    summary = (qna_summary[:1200] + "...") if qna_summary and len(qna_summary) > 1200 else (qna_summary or "N/A")

    prompt = f"""You are a senior interviewer writing a professional scorecard.
Candidate: {name} | Role: {role} | Skills: {skills_str}
Scores: Technical {technical_avg:.0f}/100, Communication {communication_avg:.0f}/100. Per-skill: {skill_scores_str}
Interview summary: {summary}

Generate JSON: {{"communication_review": "2-3 sentences on clarity, grammar, articulation", "recommendation": "2-3 sentence hiring recommendation with reasoning", "skill_wise_reviews": {{"SkillName": "1-2 sentence review"}}}}
skill_wise_reviews keys must be exactly: {skill_keys}
Return ONLY valid JSON."""

    try:
        response = client.models.generate_content(
            model=MODEL_NAME, contents=prompt,
            config={"max_output_tokens": 800, "temperature": 0.4}
        )
        m = re.search(r"\{.*\}", response.text.strip(), re.DOTALL)
        if m:
            return json.loads(m.group())
    except Exception:
        pass
    comm = "Excellent communication." if communication_avg >= 80 else "Average communication." if communication_avg >= 60 else "Communication needs improvement."
    rec = "Strong candidate. Recommend for the role." if technical_avg >= 80 else "Average performance. Consider probation." if technical_avg >= 60 else "Below expectations."
    skill_reviews = {k: ("Strong." if v >= 80 else "Adequate." if v >= 60 else "Needs improvement.") for k, v in (skill_breakdown or {}).items()}
    return {"communication_review": comm, "recommendation": rec, "skill_wise_reviews": skill_reviews}


import random

def calculate_scores(qna_data):
    print("interview_details-:", qna_data)
    """
    qna_data: list of dicts
        [
            {
                "question": "...",
                "answer": "...",
                "ai_response": { "technical_score": .., "communication_score": .., "skill_breakdown": {...} }
            },
            ...
        ]
    Returns dict with:
        technical_avg, communication_avg, skill_breakdown, communication_review
    """

    if not qna_data:
        return {
            "technical_avg": 0,
            "communication_avg": 0,
            "skill_breakdown": {},
            "communication_review": "No answers provided."
        }

    total_tech = 0
    total_comm = 0
    skill_totals = {}
    skill_counts = {}

    for item in qna_data:
        ai_resp = item.get("ai_response", {})

        # If user did not answer or AI couldn't evaluate, set scores to 0
        if not item.get("answer") or not ai_resp:
            tech = 0
            comm = 0
            skill_breakdown = {}
        else:
            tech = ai_resp.get("technical_score", 0)
            comm = ai_resp.get("communication_score", 0)
            skill_breakdown = ai_resp.get("skill_breakdown", {})

        total_tech += tech
        total_comm += comm

        # Skill breakdown aggregation
        for skill, score in skill_breakdown.items():
            if skill in skill_totals:
                skill_totals[skill] += score
                skill_counts[skill] += 1
            else:
                skill_totals[skill] = score
                skill_counts[skill] = 1

    count = len(qna_data)
    technical_avg = round(total_tech / count, 2)
    communication_avg = round(total_comm / count, 2)

    # Average skill scores
    final_skill_breakdown = {}
    for skill, total in skill_totals.items():
        final_skill_breakdown[skill] = round(total / skill_counts[skill], 2)

    # Communication review
    if communication_avg >= 80:
        communication_review = "Excellent communication skills."
    elif communication_avg >= 60:
        communication_review = "Average communication skills, could improve."
    else:
        communication_review = "Poor communication skills, needs improvement."

    return {
        "technical_avg": technical_avg,
        "communication_avg": communication_avg,
        "skill_breakdown": final_skill_breakdown,
        "communication_review": communication_review
    }
