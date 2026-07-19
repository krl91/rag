"""
kb_smart_metering — Système de gestion des connaissances projet (smart metering).

Package principal. Expose la version du projet.
"""

import asyncio
import sys

# Windows : ProactorEventLoop (défaut >= 3.8) est incompatible avec le driver
# neo4j async (sockets SSL) et peut provoquer des RuntimeError dans uvicorn.
# SelectorEventLoop est le comportement attendu sur toutes les plateformes.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

__version__ = "0.1.0"
