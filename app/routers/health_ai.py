from fastapi import APIRouter
from pydantic import BaseModel

from app.services.health_ai import generate_health_advice


router = APIRouter(tags=["health-ai"])


class HealthAdviceRequest(BaseModel):
    symptoms: str


@router.post("/health/advice")
def health_advice(body: HealthAdviceRequest):
    return generate_health_advice(body.symptoms)
