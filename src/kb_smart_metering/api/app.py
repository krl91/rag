"""
Application FastAPI principale.

Non implémentée dans cette phase. Squelette documenté.
"""

import logging

from fastapi import FastAPI

from kb_smart_metering.api.routes import router

logger = logging.getLogger(__name__)

app = FastAPI(
    title="kb-smart-metering",
    description="API de gestion des connaissances projet smart metering",
    version="0.1.0",
)

app.include_router(router)
