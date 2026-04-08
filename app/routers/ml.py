from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

router = APIRouter(tags=["confidence"])


class ConfidenceQuery(BaseModel):
    app_report_count_30m: int | None = Field(0, alias="app_reports")
    whatsapp_report_count_30m: int | None = Field(0, alias="whatsapp_reports")
    news_signal_count_1h: int | None = Field(0, alias="news_reports")
    social_signal_count_1h: int | None = Field(0, alias="social_reports")
    source_entropy: float | None = None
    local_grid_risk_score: float | None = None
    weather_severity: float | None = None
    nearby_ready_responders: int | None = None
    eonet_event_count_24h: int | None = None
    responders_ready_flag: bool | None = None


class ConfidenceRequest(BaseModel):
    report_counts: dict[str, int] = Field(default_factory=dict)
    source_entropy: float | None = None
    local_grid_risk_score: float | None = None
    weather_severity: float | None = None
    nearby_ready_responders: int | None = None
    eonet_event_count_24h: int | None = None
    responder_toggle: dict[str, bool] | None = None


class ConfidenceResponse(BaseModel):
    model_version: str
    base_confidence: float
    confidence: float
    reasons: list[str]
    fallback_used: bool


def _rule_confidence(payload: ConfidenceRequest) -> tuple[float, list[str]]:
    reasons: list[str] = []
    score = 0.5

    sources = sum(payload.report_counts.values())
    if sources >= 3:
        score += 0.1
        reasons.append("Multiple sources in last 30m")
    if payload.weather_severity and payload.weather_severity >= 7:
        score += 0.15
        reasons.append("High weather severity")
    if payload.local_grid_risk_score and payload.local_grid_risk_score >= 70:
        score += 0.1
        reasons.append("Grid risk score is high")
    if payload.nearby_ready_responders and payload.nearby_ready_responders >= 2:
        score += 0.05
        reasons.append("Ready responders nearby")
    if payload.eonet_event_count_24h and payload.eonet_event_count_24h >= 1:
        score += 0.05
        reasons.append("Nearby EONET signal")

    score = min(score, 0.95)
    return score, reasons


def _assemble_request(query: ConfidenceQuery) -> ConfidenceRequest:
    return ConfidenceRequest(
        report_counts={
            "app": query.app_report_count_30m or 0,
            "whatsapp": query.whatsapp_report_count_30m or 0,
            "news": query.news_signal_count_1h or 0,
            "social": query.social_signal_count_1h or 0,
        },
        source_entropy=query.source_entropy,
        local_grid_risk_score=query.local_grid_risk_score,
        weather_severity=query.weather_severity,
        nearby_ready_responders=query.nearby_ready_responders,
        eonet_event_count_24h=query.eonet_event_count_24h,
        responder_toggle={"ready": bool(query.responders_ready_flag)} if query.responders_ready_flag is not None else None,
    )


@router.get("/ml/confidence/score", response_model=ConfidenceResponse)
def score_confidence(query: ConfidenceQuery = Depends()):
    payload = _assemble_request(query)
    base, reasons = _rule_confidence(payload)
    final = base
    penalty_notes: list[str] = []

    if payload.source_entropy is not None and payload.source_entropy < 0.5:
        final *= 0.9
        penalty_notes.append("Low source entropy")
    if payload.responder_toggle and not any(payload.responder_toggle.values()):
        final *= 0.85
        penalty_notes.append("No responders reported ready")

    final = max(0.0, min(1.0, final))
    reasons.extend(penalty_notes)

    return ConfidenceResponse(
        model_version="confidence_rule_v1",
        base_confidence=round(base, 3),
        confidence=round(final, 3),
        reasons=reasons or ["Rule-based baseline used"],
        fallback_used=True,
    )
