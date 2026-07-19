"""
Extracteur Confluence — collecte les pages d'un espace depuis l'API Confluence.

Convertit le storage format (HTML-like) en texte brut, récupère les commentaires
et l'historique de versions via atlassian-python-api.
"""

import logging
from datetime import datetime
from html.parser import HTMLParser
from typing import Optional

from atlassian import Confluence

from kb_smart_metering.normalize.models import RawDocument

logger = logging.getLogger(__name__)

_PAGE_SIZE = 50


class _TextExtractor(HTMLParser):
    """Convertit du HTML / storage-format Confluence en texte brut."""

    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []

    def handle_data(self, data: str) -> None:
        stripped = data.strip()
        if stripped:
            self._parts.append(stripped)

    def get_text(self) -> str:
        return "\n".join(self._parts)


def _storage_to_text(storage_body: str) -> str:
    """Convertit le format de stockage Confluence en texte brut."""
    parser = _TextExtractor()
    try:
        parser.feed(storage_body)
    except Exception:
        pass
    return parser.get_text()


class ConfluenceExtractor:
    """Extracteur de pages Confluence via atlassian-python-api."""

    def __init__(self, url: str, token: str, space_key: str) -> None:
        """
        Initialise l'extracteur Confluence.

        Args:
            url: URL de base de l'instance Confluence.
            token: Token d'API Confluence.
            space_key: Clé de l'espace à extraire (ex. « ARCH »).
        """
        self._confluence = Confluence(url=url, token=token)
        self._space_key = space_key

    def extract(self) -> list[RawDocument]:
        """Extrait toutes les pages de l'espace Confluence configuré."""
        documents: list[RawDocument] = []
        start = 0

        while True:
            logger.debug("Confluence espace=%r start=%d", self._space_key, start)
            try:
                pages = self._confluence.get_all_pages_from_space(
                    self._space_key,
                    start=start,
                    limit=_PAGE_SIZE,
                    expand="body.storage,version,history,metadata.labels",
                )
            except Exception as exc:
                logger.error(
                    "Erreur lors de la requête Confluence (start=%d) : %s", start, exc
                )
                break

            if not pages:
                break

            for page in pages:
                doc = self._page_to_raw(page)
                if doc:
                    documents.append(doc)

            if len(pages) < _PAGE_SIZE:
                break
            start += len(pages)

        logger.info(
            "Confluence : %d pages extraites (espace=%s)", len(documents), self._space_key
        )
        return documents

    def _page_to_raw(self, page: dict) -> Optional[RawDocument]:
        """Convertit une page Confluence en RawDocument."""
        try:
            page_id: str = str(page["id"])
            title: str = page.get("title") or "(sans titre)"

            body = page.get("body", {}).get("storage", {}).get("value", "")
            contenu = _storage_to_text(body)

            # Commentaires
            try:
                comments_data = self._confluence.get_page_comments(
                    page_id, expand="body.view.value", depth="all"
                )
                comments = (
                    comments_data.get("results", [])
                    if isinstance(comments_data, dict)
                    else []
                )
            except Exception:
                comments = []

            comments_text = "\n\n".join(
                f"[{c.get('author', {}).get('displayName', '?')}] "
                + _storage_to_text(c.get("body", {}).get("view", {}).get("value", ""))
                for c in comments
            )

            version_info = page.get("version", {})
            history_info = page.get("history", {})
            created_by = history_info.get("createdBy", {}).get("displayName")

            content_parts: list[str] = [contenu]
            if comments_text:
                content_parts.append("=== Commentaires ===\n" + comments_text)

            space_key = page.get("space", {}).get("key", self._space_key)
            url = f"{self._confluence.url}/wiki/spaces/{space_key}/pages/{page_id}"

            return RawDocument(
                id_source=page_id,
                source_type="confluence",
                titre=title,
                contenu_texte="\n\n".join(p for p in content_parts if p),
                auteur=created_by,
                date_creation=_parse_dt(history_info.get("createdDate")),
                date_modification=_parse_dt(version_info.get("when")),
                url_ou_chemin=url,
                metadonnees={
                    "space_key": space_key,
                    "version_number": version_info.get("number"),
                    "nb_comments": len(comments),
                    "labels": [
                        lbl.get("name")
                        for lbl in page.get("metadata", {})
                        .get("labels", {})
                        .get("results", [])
                    ],
                },
            )
        except Exception as exc:
            logger.error("Impossible de convertir la page %s : %s", page.get("id"), exc)
            return None


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    """Parse une date ISO 8601."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None
