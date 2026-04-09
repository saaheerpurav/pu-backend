"""
WhatsApp Bot Router — Twilio webhook

Flow: HELP → location → disaster type → people count → injuries → report saved → case ID returned
Broadcast: when confidence ≥ 60, alert ALL citizens stored in `users`
"""

import io
import logging
import os
import threading
from typing import Optional

import requests
from fastapi import APIRouter, Form, Request, Response
from openai import OpenAI
from pydantic import BaseModel
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse
from dotenv import load_dotenv

from app.supabase_client import supabase_admin
from app.services.language_utils import infer_language
from app.services.llm import ask_llm
from app.services.whatsapp_bot import process_message
from app.services.report_service import submit_report as _submit_report
from app.services.health_ai import generate_health_advice
from app.services.sos_service import create_sos_incident
from app.services.triage import triage_message

# Per-phone lock — prevents race conditions when user sends multiple messages quickly
_phone_locks: dict[str, threading.Lock] = {}
_locks_mutex = threading.Lock()

def get_phone_lock(phone: str) -> threading.Lock:
    with _locks_mutex:
        if phone not in _phone_locks:
            _phone_locks[phone] = threading.Lock()
        return _phone_locks[phone]

load_dotenv()

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_WHATSAPP_NUMBER = os.getenv("TWILIO_WHATSAPP_NUMBER")

CONFIDENCE_BROADCAST_THRESHOLD = 60.0
_openai_client: OpenAI | None = None
logger = logging.getLogger("resqnet.whatsapp")
router = APIRouter(prefix="/whatsapp", tags=["whatsapp"])


def get_openai_client() -> OpenAI:
    global _openai_client
    if _openai_client is None:
        _openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    return _openai_client


def twiml_reply(message: str) -> Response:
    resp = MessagingResponse()
    msg = resp.message(message)
    return Response(content=str(resp), media_type="application/xml")


def get_twilio_client() -> Client:
    return Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)


def send_whatsapp(to: str, body: str):
    """Send a single outbound WhatsApp message via Twilio."""
    try:
        get_twilio_client().messages.create(
            from_=TWILIO_WHATSAPP_NUMBER,
            to=to,
            body=body,
        )
    except Exception as e:
        print(f"[Twilio] Failed to send to {to}: {e}")


def log_chatbot_exchange(message: str, response: str):
    try:
        supabase_admin.table("chatbot_logs").insert({
            "message": message,
            "response": response,
        }).execute()
    except Exception:
        pass


def transcribe_voice_note(media_url: str, media_type: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    if not media_url:
        return None, None

    try:
        media_resp = requests.get(
            media_url,
            auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN),
            timeout=15,
        )
        media_resp.raise_for_status()
        client = get_openai_client()
        audio_stream = io.BytesIO(media_resp.content)
        ext = "ogg"
        detected_type = (media_type or media_resp.headers.get("Content-Type", "")).split(";")[0].strip().lower()
        if detected_type in ("audio/mp3", "audio/mpeg"):
            ext = "mp3"
        elif detected_type in ("audio/wav", "audio/x-wav"):
            ext = "wav"
        elif detected_type in ("audio/m4a",):
            ext = "m4a"
        elif detected_type in ("audio/webm",):
            ext = "webm"
        elif detected_type in ("audio/ogg", "audio/ogv"):
            ext = "ogg"
        audio_stream.name = f"voice.{ext}"
        transcript = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_stream,
        )
        return transcript.text, getattr(transcript, "language", None)
    except Exception as exc:
        logger.warning("WhatsApp STT error: %s", exc)
        return None, None


def normalize_phone(phone: str) -> tuple[str, str]:
    raw = (phone or "").strip()
    stripped = raw.replace("whatsapp:", "")
    return raw, stripped


def find_user_by_phone(phone: str) -> dict | None:
    raw, stripped = normalize_phone(phone)
    for candidate in (raw, stripped):
        if not candidate:
            continue
        try:
            res = supabase_admin.table("users").select("*").eq("phone", candidate).limit(1).execute()
            if res.data:
                return res.data[0]
        except Exception:
            continue
    return None


def get_all_citizen_phones() -> list[str]:
    """
    Fetch phone numbers of all users who signed up via mobile app.
    Returns list of Twilio-formatted strings: ["whatsapp:+91...", ...]
    """
    try:
        res = supabase_admin.table("users") \
            .select("phone") \
            .eq("role", "citizen") \
            .not_.is_("phone", "null") \
            .execute()

        numbers = []
        for row in (res.data or []):
            phone = row.get("phone", "").strip()
            if phone:
                # Normalise to whatsapp: prefix
                wa_number = phone if phone.startswith("whatsapp:") else f"whatsapp:{phone}"
                numbers.append(wa_number)
        return numbers
    except Exception as e:
        print(f"[Broadcast] Failed to fetch citizen phones: {e}")
        return []


def broadcast_alert(event: dict, report_id: str):
    """
    Send alert to ALL citizens registered via mobile app.
    Only fires when event confidence >= CONFIDENCE_BROADCAST_THRESHOLD.
    """
    numbers = get_all_citizen_phones()
    if not numbers:
        print("[Broadcast] No citizen phones found — skipping broadcast.")
        return

    severity_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(event.get("severity", "low"), "⚪")
    message = (
        f"{severity_emoji} *ResQNet ALERT*\n\n"
        f"*Disaster:* {event['type'].title()}\n"
        f"*Severity:* {event.get('severity', 'unknown').upper()}\n"
        f"*Confidence:* {event.get('confidence', 0):.1f}%\n"
        f"*Location:* {event['latitude']:.4f}, {event['longitude']:.4f}\n"
        f"*Case Ref:* {report_id[:8].upper()}\n\n"
        f"⚠️ Stay alert. Follow local authority instructions.\n"
        f"_Reply HELP if you need emergency assistance._"
    )

    print(f"[Broadcast] Sending alert to {len(numbers)} citizen(s)...")
    for number in numbers:
        send_whatsapp(number, message)


def quick_whatsapp_router(phone: str, body: str, latitude: float | None, longitude: float | None) -> str | None:
    text = (body or "").strip().lower()
    if not text:
        return None

    if any(keyword in text for keyword in ("pain", "injury", "bleeding", "cut", "burn", "fever", "wound", "cough", "vomit", "chest", "breath", "blood")):
        advice = generate_health_advice(body)
        response = (
            f"Severity: {advice['severity']}\n"
            f"Steps: {' '.join(advice['steps'])}\n"
            f"Medicines: {', '.join(advice['medicines'])}"
        )
        log_chatbot_exchange(body, response)
        return response

    if "flood" in text:
        response = (
            "Mock shelters nearby:\n"
            "1. Town Hall Relief Camp\n"
            "2. Community School Shelter\n"
            "3. Metro Station High Ground"
        )
        log_chatbot_exchange(body, response)
        return response

    return None


def handle_whatsapp_webhook(
    From: str,
    Body: str = "",
    Latitude: str = None,
    Longitude: str = None,
    NumMedia: str = "0",
    MediaUrl0: str = None,
    MediaContentType0: str = None,
):
    phone = From
    lat = float(Latitude) if Latitude else None
    lng = float(Longitude) if Longitude else None

    text_body = Body or ""
    num_media = int(NumMedia or "0")
    media_type = (MediaContentType0 or "").lower()
    voice_message = bool(MediaUrl0) and "audio" in media_type
    if voice_message:
        transcribed, _language = transcribe_voice_note(MediaUrl0, MediaContentType0)
        if transcribed:
            text_body = transcribed
            Body = transcribed
        else:
            logger.warning("Failed to transcribe WhatsApp voice note for %s", phone)
            text_body = "voice note"
            Body = text_body
        logger.info("WhatsApp voice transcript for %s: %s", phone, text_body.replace("\n", " "))

    Body = Body or text_body
    language_hint = infer_language(text_body)
    quick_response = None if voice_message else quick_whatsapp_router(phone, text_body, lat, lng)
    if voice_message and not quick_response:
        logger.info("Routing voice transcript to LLM for %s", phone)
        return twiml_reply(ask_llm(text_body, language_hint=language_hint))
    if quick_response:
        return twiml_reply(quick_response)

    # Acquire per-phone lock — if this phone is already being processed, queue this message
    lock = get_phone_lock(phone)
    with lock:
        reply_text, completed_report = process_message(phone, Body, lat, lng)

        # ── Flow not complete yet — just reply ────────────────────
        if completed_report is None:
            return twiml_reply(reply_text)

        # ── Flow complete — submit report directly (no HTTP round-trip) ──
        try:
            result = _submit_report(
                source=completed_report["source"],
                latitude=completed_report["latitude"],
                longitude=completed_report["longitude"],
                disaster_type=completed_report["disaster_type"],
                description=completed_report.get("description"),
                people_count=completed_report.get("people_count", 1),
                injuries=completed_report.get("injuries", False),
            )
        except Exception as e:
            print(f"[WhatsApp] Report submission failed: {e}")
            return twiml_reply(
                "⚠️ We had trouble saving your report. "
                "Please call emergency services if in immediate danger.\n\n*Dial 112*"
            )

        report_id = result.get("report_id") or "unknown"
        event_id = result.get("event_id")
        confidence = result.get("confidence", 0)

        # ── Confirmation to reporting user ────────────────────────
        injuries_note = "🚑 Injuries flagged — priority response activated." if completed_report.get("injuries") else ""
        confirmation = (
            f"✅ *Emergency Report Logged*\n\n"
            f"*Case ID:* `{report_id[:8].upper()}`\n"
            f"*Type:* {completed_report['disaster_type'].title()}\n"
            f"*People:* {completed_report.get('people_count', 1)}\n"
            f"{injuries_note}\n"
            f"Help is being coordinated. Stay safe.\n\n"
            f"_Send HELP to submit another report._"
        ).strip()

        # ── Broadcast to all citizens if threshold hit ────────────
        if confidence >= CONFIDENCE_BROADCAST_THRESHOLD and event_id:
            try:
                event_res = supabase_admin.table("disaster_events") \
                    .select("*").eq("id", event_id).single().execute()
                if event_res.data:
                    # Run broadcast in background so it doesn't delay the reply
                    t = threading.Thread(
                        target=broadcast_alert,
                        args=(event_res.data, report_id),
                        daemon=True,
                    )
                    t.start()
            except Exception as e:
                print(f"[WhatsApp] Broadcast error: {e}")

        return twiml_reply(confirmation)


@router.post("/webhook")
def whatsapp_webhook(
    From: str = Form(...),
    Body: str = Form(default=""),
    Latitude: str = Form(default=None),
    Longitude: str = Form(default=None),
    NumMedia: str = Form(default="0"),
    MediaUrl0: str = Form(default=None),
    MediaContentType0: str = Form(default=None),
):
    return handle_whatsapp_webhook(
        From,
        Body,
        Latitude,
        Longitude,
        NumMedia,
        MediaUrl0,
        MediaContentType0,
    )


class WhatsAppTriageRequest(BaseModel):
    phone: str
    message: str
    latitude: float | None = None
    longitude: float | None = None
    language: str | None = None


class WhatsAppEscalateRequest(BaseModel):
    phone: str
    triage_result: dict
    latitude: float | None = None
    longitude: float | None = None


@router.post("/triage")
def whatsapp_triage(body: WhatsAppTriageRequest):
    context = []
    if body.latitude is not None and body.longitude is not None:
        context.append(f"Location: {body.latitude}, {body.longitude}")
    triage = triage_message(
        body.message,
        feature="whatsapp-triage",
        language_hint=body.language,
        extra_context=" ".join(context),
    )
    return {
        "phone": body.phone,
        "latitude": body.latitude,
        "longitude": body.longitude,
        "triage": triage,
    }


@router.post("/triage/escalate")
def whatsapp_escalate(body: WhatsAppEscalateRequest):
    intent = body.triage_result or {}
    severity = intent.get("severity")
    incident_type = "medical" if severity in ("high", "medium") else "disaster"
    user = find_user_by_phone(body.phone)
    result = create_sos_incident(
        user_id=user.get("id") if user else None,
        incident_type=incident_type,
        latitude=body.latitude,
        longitude=body.longitude,
        source="whatsapp",
    )
    responder = result.get("responder") or {}
    reply_text = (
        f"🚨 Emergency escalated. Incident {result['incident_id'][:8].upper()} "
        f"is {result['status']}."
    )
    if responder:
        reply_text += f" Responder: {responder.get('type')} (ETA {responder.get('eta')})."
    else:
        reply_text += " No responder available right now; we will update you ASAP."

    return {
        "incident_id": result["incident_id"],
        "status": result["status"],
        "reply_text": reply_text,
        "responder": responder,
    }


@router.get("/status")
def bot_status():
    """Check bot config and how many citizens can receive broadcasts."""
    citizen_count = len(get_all_citizen_phones())
    return {
        "configured": bool(TWILIO_ACCOUNT_SID and not TWILIO_ACCOUNT_SID.startswith("ACx")),
        "whatsapp_number": TWILIO_WHATSAPP_NUMBER,
        "broadcast_reach": citizen_count,
    }
