"""
WhatsApp Conversation State Machine

States per user (keyed by WhatsApp number):
  idle → awaiting_location → awaiting_type → awaiting_people → awaiting_injuries → done

Stored in-memory (sufficient for hackathon).
"""

from datetime import datetime, timezone, timedelta
from app.services.llm import ask_llm

# In-memory session store: { "whatsapp:+91..." : { state, data, updated_at } }
sessions: dict = {}

SESSION_TIMEOUT_MINUTES = 15

DISASTER_TYPES = {
    "1": "flood",
    "2": "fire",
    "3": "earthquake",
    "4": "landslide",
    "5": "other",
    "flood": "flood",
    "fire": "fire",
    "earthquake": "earthquake",
    "landslide": "landslide",
    "other": "other",
}

MESSAGES = {
    "welcome": (
        "🚨 *ResQNet Emergency Bot*\n\n"
        "Hello! I'll help log your emergency report.\n\n"
        "Please *share your location* using WhatsApp's location feature, "
        "or type your area name (e.g. _Koramangala, Bangalore_)."
    ),
    "ask_type": (
        "Got your location. ✅\n\n"
        "What type of disaster is this?\n\n"
        "1️⃣ Flood\n"
        "2️⃣ Fire\n"
        "3️⃣ Earthquake\n"
        "4️⃣ Landslide\n"
        "5️⃣ Other\n\n"
        "Reply with a number or the disaster name."
    ),
    "ask_people": (
        "Understood. How many people are affected or need help?\n"
        "_(Type a number, e.g. 5)_"
    ),
    "ask_injuries": (
        "Are there any injuries?\n\n"
        "Reply *YES* or *NO*"
    ),
    "invalid_type": (
        "Please reply with a number 1–5 or the disaster name.\n\n"
        "1️⃣ Flood  2️⃣ Fire  3️⃣ Earthquake  4️⃣ Landslide  5️⃣ Other"
    ),
    "invalid_people": (
        "Please reply with a number (e.g. 3)."
    ),
    "invalid_injuries": (
        "Please reply *YES* or *NO*."
    ),
    "not_started": (
        "Send *HELP* to report an emergency."
    ),
}


def get_session(phone: str) -> dict:
    session = sessions.get(phone)
    if session:
        # Expire stale sessions
        age = datetime.now(timezone.utc) - session["updated_at"]
        if age > timedelta(minutes=SESSION_TIMEOUT_MINUTES):
            del sessions[phone]
            return None
    return session


def set_session(phone: str, state: str, data: dict):
    sessions[phone] = {
        "state": state,
        "data": data,
        "updated_at": datetime.now(timezone.utc),
    }


def clear_session(phone: str):
    sessions.pop(phone, None)


def process_message(
    phone: str,
    body: str,
    latitude: float = None,
    longitude: float = None,
) -> tuple[str, dict | None]:
    """
    Process an incoming WhatsApp message.

    Returns:
        (reply_text, completed_report_or_None)

    completed_report is a dict ready to POST to /reports if the flow is done.
    """
    text = body.strip().lower() if body else ""
    session = get_session(phone)

    # ── Trigger word ──────────────────────────────────────────────
    if text in ("help", "sos", "emergency", "hi", "hello", "start"):
        set_session(phone, "awaiting_location", {})
        return MESSAGES["welcome"], None

    # ── No active session — hand off to LLM for general queries ──
    if not session:
        reply = ask_llm(body)
        return reply, None

    state = session["state"]
    data = session["data"]

    # ── STEP 1: Location ─────────────────────────────────────────
    if state == "awaiting_location":
        if latitude is not None and longitude is not None:
            # WhatsApp location pin shared
            data["latitude"] = latitude
            data["longitude"] = longitude
            data["location_text"] = f"{latitude:.4f}, {longitude:.4f}"
        else:
            # Text location — use Bangalore centre as default lat/lng
            # In production, geocode this with Nominatim
            data["latitude"] = 12.9716
            data["longitude"] = 77.5946
            data["location_text"] = body.strip()

        set_session(phone, "awaiting_type", data)
        return MESSAGES["ask_type"], None

    # ── STEP 2: Disaster type ────────────────────────────────────
    if state == "awaiting_type":
        disaster = DISASTER_TYPES.get(text)
        if not disaster:
            return MESSAGES["invalid_type"], None

        data["disaster_type"] = disaster
        set_session(phone, "awaiting_people", data)
        return MESSAGES["ask_people"], None

    # ── STEP 3: People count ─────────────────────────────────────
    if state == "awaiting_people":
        if not text.isdigit():
            return MESSAGES["invalid_people"], None

        data["people_count"] = int(text)
        set_session(phone, "awaiting_injuries", data)
        return MESSAGES["ask_injuries"], None

    # ── STEP 4: Injuries ─────────────────────────────────────────
    if state == "awaiting_injuries":
        if text in ("yes", "y"):
            data["injuries"] = True
        elif text in ("no", "n"):
            data["injuries"] = False
        else:
            return MESSAGES["invalid_injuries"], None

        clear_session(phone)
        report = {
            "source": "whatsapp",
            "latitude": data["latitude"],
            "longitude": data["longitude"],
            "disaster_type": data["disaster_type"],
            "description": f"WhatsApp report from {phone}. Location: {data.get('location_text', 'unknown')}",
            "people_count": data["people_count"],
            "injuries": data["injuries"],
        }
        return None, report  # Caller will submit report and build reply

    # Shouldn't reach here — fallback to LLM
    reply = ask_llm(body)
    return reply, None
