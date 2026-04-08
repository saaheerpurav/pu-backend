import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.routers import (
    ai_insights,
    auth,
    dashboard,
    devices,
    dispatch,
    external,
    events,
    grid,
    health_ai,
    incidents,
    media,
    news,
    nfc,
    predictions,
    reports,
    rescue,
    responders,
    routes,
    routing,
    simulation,
    social,
    sos,
    wearables,
    whatsapp,
    whatsapp_alias,
    ml,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s %(name)s: %(message)s",
    force=True,
)

logger = logging.getLogger("resqnet.backend")

app = FastAPI(title="ResQNet API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info("request %s %s", request.method, request.url.path)
    try:
        response = await call_next(request)
        logger.info(
            "response %s %s %s",
            request.method,
            request.url.path,
            response.status_code,
        )
        return response
    except Exception:  # pragma: no cover
        logger.exception("unhandled error on %s %s", request.method, request.url.path)
        raise


@app.exception_handler(Exception)
async def log_exceptions(request: Request, exc: Exception):
    logger.exception("caught global exception %s %s", request.method, request.url.path)
    return JSONResponse({"detail": "Internal server error"}, status_code=500)

app.include_router(auth.router)
app.include_router(reports.router)
app.include_router(events.router)
app.include_router(rescue.router)
app.include_router(grid.router)
app.include_router(predictions.router)
app.include_router(simulation.router)
app.include_router(dashboard.router)
app.include_router(external.router)
app.include_router(ai_insights.router)
app.include_router(whatsapp.router)
app.include_router(devices.router)
app.include_router(responders.router)
app.include_router(incidents.router)
app.include_router(dispatch.router)
app.include_router(social.router)
app.include_router(news.router)
app.include_router(media.router)
app.include_router(sos.router)
app.include_router(routes.router)
app.include_router(routing.router)
app.include_router(health_ai.router)
app.include_router(wearables.router)
app.include_router(nfc.router)
app.include_router(whatsapp_alias.router)
app.include_router(ml.router)


@app.get("/")
def root():
    return {"status": "ResQNet API running", "version": "1.0.0"}


@app.get("/health")
def health():
    return {"status": "ok"}
