"""
Extracteur de transcriptions de réunions — parse les fichiers .txt et .vtt.

Détecte les segments horodatés et identifie les participants par pattern matching.
Supporte les formats texte libre et WebVTT (Teams, Zoom, etc.).
"""

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Union

from kb_smart_metering.normalize.models import RawDocument, normalize_file_source_id

logger = logging.getLogger(__name__)

# Pattern horodatage dans les fichiers TXT : [HH:MM:SS] ou [HH:MM] en début de ligne
_RE_TIMESTAMP_TXT = re.compile(
    r"^\[?(\d{1,2}:\d{2}(?::\d{2})?(?:\.\d+)?)\]?\s+(.*)"
)

# Pattern timestamp VTT : HH:MM:SS.mmm --> HH:MM:SS.mmm
_RE_VTT_TIMESTAMP = re.compile(
    r"^(\d{1,2}:\d{2}:\d{2}\.\d{3})\s+-->\s+\d{1,2}:\d{2}:\d{2}\.\d{3}"
)

# Détection d'un speaker : "Prénom Nom: texte" ou "Prénom: texte"
# Le nom commence par une majuscule et ne contient pas de ':' avant le ':'
_RE_SPEAKER = re.compile(r"^([A-ZÀÂÄÉÈÊËÎÏÔÙÛÜ][^:\n]{1,60}):\s+(.+)$")


@dataclass
class _Segment:
    """Segment de transcription avec horodatage et participant optionnels."""

    timestamp: Optional[str]
    speaker: Optional[str]
    text: str


class MeetingExtractor:
    """Extracteur de transcriptions de réunions (.txt / .vtt)."""

    def __init__(self, file_path: Union[str, Path]) -> None:
        """
        Args:
            file_path: Chemin vers le fichier de transcription (.txt ou .vtt).
        """
        self._file_path = Path(file_path)

    def extract(self) -> list[RawDocument]:
        """Extrait les segments et les participants depuis la transcription."""
        if not self._file_path.exists():
            logger.error("Fichier introuvable : %s", self._file_path)
            return []

        try:
            content = self._file_path.read_text(encoding="utf-8", errors="replace")
        except Exception as exc:
            logger.error("Impossible de lire %s : %s", self._file_path, exc)
            return []

        suffix = self._file_path.suffix.lower()
        segments = _parse_vtt(content) if suffix == ".vtt" else _parse_txt(content)

        if not segments:
            logger.warning("Aucun segment extrait de %s", self._file_path)
            return []

        participants: set[str] = set()
        lines: list[str] = []
        for seg in segments:
            if seg.speaker:
                participants.add(seg.speaker)
            prefix = f"[{seg.timestamp}] " if seg.timestamp else ""
            speaker_part = f"{seg.speaker}: " if seg.speaker else ""
            lines.append(f"{prefix}{speaker_part}{seg.text}")

        stat = self._file_path.stat()
        logger.info(
            "Meeting : %d segment(s), %d participant(s) — %s",
            len(segments),
            len(participants),
            self._file_path.name,
        )

        return [
            RawDocument(
                id_source=normalize_file_source_id(self._file_path),
                source_type="meeting",
                titre=self._file_path.stem,
                contenu_texte="\n".join(lines),
                url_ou_chemin=self._file_path.resolve().as_uri(),
                metadonnees={
                    "format": suffix.lstrip("."),
                    "nb_segments": len(segments),
                    "participants": sorted(participants),
                    "taille_octets": stat.st_size,
                },
            )
        ]


def _parse_vtt(content: str) -> list[_Segment]:
    """Parse un fichier WebVTT et retourne les segments horodatés."""
    segments: list[_Segment] = []
    lines = content.splitlines()
    i = 0

    # Chercher et sauter l'en-tête WEBVTT
    while i < len(lines) and not lines[i].startswith("WEBVTT"):
        i += 1
    i += 1

    current_ts: Optional[str] = None
    text_lines: list[str] = []

    def _flush() -> None:
        nonlocal current_ts, text_lines
        if text_lines:
            full = " ".join(text_lines).strip()
            m = _RE_SPEAKER.match(full)
            if m:
                segments.append(_Segment(current_ts, m.group(1).strip(), m.group(2).strip()))
            else:
                segments.append(_Segment(current_ts, None, full))
        current_ts = None
        text_lines = []

    while i < len(lines):
        line = lines[i].strip()

        m_ts = _RE_VTT_TIMESTAMP.match(line)
        if m_ts:
            _flush()
            current_ts = m_ts.group(1)
        elif line == "" or (line.isdigit() and current_ts is None):
            # Ligne vide ou numéro de cue → délimiteur
            if text_lines:
                _flush()
        elif line.startswith("NOTE"):
            pass  # commentaire VTT, ignorer
        else:
            if current_ts is not None or text_lines:
                text_lines.append(line)

        i += 1

    _flush()
    return segments


def _parse_txt(content: str) -> list[_Segment]:
    """Parse une transcription texte avec horodatages optionnels."""
    segments: list[_Segment] = []

    for line in content.splitlines():
        line = line.strip()
        if not line:
            continue

        m_ts = _RE_TIMESTAMP_TXT.match(line)
        if m_ts:
            timestamp = m_ts.group(1)
            rest = m_ts.group(2).strip()
            m_sp = _RE_SPEAKER.match(rest)
            if m_sp:
                segments.append(
                    _Segment(timestamp, m_sp.group(1).strip(), m_sp.group(2).strip())
                )
            else:
                segments.append(_Segment(timestamp, None, rest))
        else:
            m_sp = _RE_SPEAKER.match(line)
            if m_sp:
                segments.append(
                    _Segment(None, m_sp.group(1).strip(), m_sp.group(2).strip())
                )
            else:
                segments.append(_Segment(None, None, line))

    return segments
