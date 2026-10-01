import json
import os
import time

from dotenv import load_dotenv
from google import genai
from google.genai import types

# IMPORTANT: load .env BEFORE reading environment variables
load_dotenv()

MODELS = [
    m.strip()
    for m in os.getenv(
        "GEMINI_MODELS", "gemini-3.8-flash,gemini-3.7-flash,gemini-3.1-flash-lite"
    ).split(",")
    if m.strip()
]

MAX_RESUME_CHARS = 15000
_client = None


def get_client():
    """Create the Gemini client on first use (so the app can still start without a key)."""
    global _client
    if _client is None:
        key = os.getenv("GEMINI_API_KEY")
        if not key:
            raise ValueError("GEMINI_API_KEY is not set. Add it to your .env file.")
        _client = genai.Client(api_key=key)
    return _client


def _clean_list(value):
    """Make sure every list item is a plain string (models sometimes return objects)."""
    if not isinstance(value, list):
        return []
    out = []
    for item in value:
        if isinstance(item, str):
            out.append(item.strip())
        elif isinstance(item, dict):
            out.append(" - ".join(str(v) for v in item.values()))
        else:
            out.append(str(item))
    return [x for x in out if x]


def _parse_json(text: str) -> dict:
    content = text.strip()
    if content.startswith("```"):
        content = content.strip("`")
        if content.lower().startswith("json"):
            content = content[4:]
    start, end = content.find("{"), content.rfind("}") + 1
    if start == -1 or end == 0:
        raise ValueError("Gemini did not return valid JSON.")
    return json.loads(content[start:end])


def analyze_resume(resume_text, user_goal):
    empty = {"skills": [], "missing_skills": [], "roadmap": [], "interview_questions": []}

    prompt = f"""
You are an expert resume analyzer and career advisor.

Analyze the resume for the target job role.

TARGET JOB ROLE:
{user_goal}

RESUME:
{resume_text[:MAX_RESUME_CHARS]}

Return ONLY valid JSON in this exact format:

{{
    "skills": [],
    "missing_skills": [],
    "roadmap": [],
    "interview_questions": []
}}

Rules:
1. Include only skills actually found in the resume.
2. Include only skills relevant to the target role.
3. Do not invent skills.
4. Identify important missing skills.
5. Create a practical roadmap (list of short text steps) for the missing skills.
6. Generate relevant interview questions (list of strings).
7. Every list item must be a plain string.
"""

    try:
        client = get_client()
    except ValueError as e:
        return {**empty, "error": str(e)}

    last_error = None

    for model_name in MODELS:
        for attempt in range(3):
            try:
                print(f"Trying Gemini model: {model_name} (attempt {attempt + 1}/3)")
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                    ),
                )
                data = _parse_json(response.text or "")
                print(f"Success with {model_name}")
                return {
                    "skills": _clean_list(data.get("skills")),
                    "missing_skills": _clean_list(data.get("missing_skills")),
                    "roadmap": _clean_list(data.get("roadmap")),
                    "interview_questions": _clean_list(data.get("interview_questions")),
                }

            except Exception as e:
                last_error = e
                text = str(e)
                print(f"Gemini error from {model_name}: {text}")

                # Retry the SAME model only for temporary overload
                if ("503" in text or "UNAVAILABLE" in text) and attempt < 2:
                    time.sleep(2 ** attempt)
                    continue
                break  # otherwise move to the next model

    return {
        **empty,
        "error": f"Gemini is temporarily unavailable. Please try again in a few minutes. Last error: {last_error}",
    }