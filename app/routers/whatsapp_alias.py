from fastapi import APIRouter, Form

from app.routers.whatsapp import handle_whatsapp_webhook


router = APIRouter(prefix="/webhook", tags=["whatsapp"])


@router.post("/whatsapp")
def whatsapp_webhook_alias(
    From: str = Form(...),
    Body: str = Form(default=""),
    Latitude: str = Form(default=None),
    Longitude: str = Form(default=None),
):
    return handle_whatsapp_webhook(From, Body, Latitude, Longitude)
