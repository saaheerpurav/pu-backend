from pydantic import BaseModel, Field
from typing import Dict, List, Optional


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
    report_counts: Dict[str, int] = Field(default_factory=dict)
    source_entropy: float | None = None
    local_grid_risk_score: float | None = None
    weather_severity: float | None = None
    nearby_ready_responders: int | None = None
    eonet_event_count_24h: int | None = None
    responder_toggle: Dict[str, bool] | None = None


class ConfidenceResponse(BaseModel):
    model_version: str
    base_confidence: float
    confidence: float
    reasons: List[str]
    fallback_used: bool
