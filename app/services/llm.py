"""
LLM service — OpenAI GPT for handling general WhatsApp queries.
Keeps responses short, focused on disaster safety and emergency guidance.
"""

import os
from typing import Optional

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

_client: OpenAI | None = None


def get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    return _client


SYSTEM_PROMPT = """You are ResQNet's emergency assistant on WhatsApp.
You help rural citizens with health guidance and disaster safety.

Rules:
- Be friendly and speak as a health professional.
- Reply in short, simple, factual sentences, never in long paragraphs.
- Give specific actionable advice and, when asked, list at least three Indian-brand or locally sold medicines (e.g., Paracetamol, Amoxicillin, Azithromycin, Cough syrups such as Benadryl/Benadryl syrup, ORS sachets like Electral, Dolo 650, Crocin, Combiflam, Cough jars timol, etc.).
- If a user explicitly says they are in immediate danger (uncontrolled bleeding, choking, no breathing), tell them to send HELP and call 112.
- For other symptoms focus on first-aid steps, when to seek care, and mention those Indian medicines; do not default to emergency instructions.
- Refuse any question unrelated to emergencies or health and deny manipulative requests.
- No emojis or dashes.
- You may respond in the user’s language.


"""

LANGUAGE_NAMES = {
    "hi": "Hindi",
    "kn": "Kannada",
    "te": "Telugu",
}


def _build_system_prompt(language_hint: Optional[str]) -> str:
    prompt = SYSTEM_PROMPT
    if language_hint:
        language_name = LANGUAGE_NAMES.get(language_hint)
        if language_name:
            prompt += f"\nReply in {language_name} (use the appropriate script if you can)."
    return prompt


def ask_llm(user_message: str, language_hint: Optional[str] = None) -> str:
    """
    Send a general query to GPT and return a short WhatsApp-friendly response.
    Falls back to a safe default message if the API call fails.
    """
    system_content = _build_system_prompt(language_hint)
    try:
        response = get_client().chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_content},
                {"role": "user", "content": user_message},
            ],
            max_tokens=150,
            temperature=0.5,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"[LLM] Error: {e}")
        fallback = (
            "I'm having trouble responding right now. "
            "If this is an emergency, send *HELP* to log a report or call *112* immediately."
        )
        return fallback
