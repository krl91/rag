"""
Extracteur de fichiers locaux — façade de rétrocompatibilité vers office.py.

Les classes WordExtractor, ExcelExtractor et PdfExtractor sont désormais
implémentées dans kb_smart_metering.extractors.office.
"""

from kb_smart_metering.extractors.office import (  # noqa: F401
    ExcelExtractor,
    PdfExtractor,
    WordExtractor,
)

import logging

logger = logging.getLogger(__name__)
