"""
Extracteur Jira — collecte les tickets (issues) depuis l'API Jira Cloud.

Gère la pagination, les commentaires, l'historique de statuts et les liens
entre tickets via atlassian-python-api.
"""

import logging
from datetime import datetime
from typing import Optional

from atlassian import Jira

from kb_smart_metering.normalize.models import RawDocument

logger = logging.getLogger(__name__)

_PAGE_SIZE = 50


class JiraExtractor:
    """Extracteur de tickets Jira via atlassian-python-api."""

    def __init__(
        self,
        url: str,
        token: str,
        jql: str = "ORDER BY updated DESC",
        max_results: Optional[int] = None,
    ) -> None:
        """
        Initialise l'extracteur Jira.

        Args:
            url: URL de base de l'instance Jira.
            token: Token d'API Jira (PAT ou token cloud).
            jql: Requête JQL pour filtrer les tickets.
            max_results: Limite optionnelle du nombre de tickets à extraire.
        """
        self._jira = Jira(url=url, token=token)
        self._jql = jql
        self._max_results = max_results

    def extract(self) -> list[RawDocument]:
        """Extrait tous les tickets correspondant au JQL configuré."""
        documents: list[RawDocument] = []
        start = 0

        while True:
            logger.debug("Jira JQL=%r start=%d", self._jql, start)
            try:
                result = self._jira.jql(
                    self._jql,
                    limit=_PAGE_SIZE,
                    start=start,
                    fields=(
                        "summary,description,status,assignee,reporter,"
                        "created,updated,comment,issuelinks"
                    ),
                    expand="changelog",
                )
            except Exception as exc:
                logger.error("Erreur lors de la requête Jira (start=%d) : %s", start, exc)
                break

            issues = result.get("issues", [])
            if not issues:
                break

            for issue in issues:
                doc = self._issue_to_raw(issue)
                if doc:
                    documents.append(doc)
                if self._max_results and len(documents) >= self._max_results:
                    break

            start += len(issues)
            if start >= result.get("total", 0):
                break
            if self._max_results and len(documents) >= self._max_results:
                break

        logger.info("Jira : %d tickets extraits", len(documents))
        return documents

    def _issue_to_raw(self, issue: dict) -> Optional[RawDocument]:
        """Convertit un issue Jira brut en RawDocument."""
        try:
            key: str = issue["key"]
            fields = issue.get("fields", {})

            summary = fields.get("summary") or "(sans titre)"
            description = fields.get("description") or ""

            # Commentaires
            comment_block = fields.get("comment", {})
            comments = (
                comment_block.get("comments", []) if isinstance(comment_block, dict) else []
            )
            comments_text = "\n\n".join(
                f"[{c.get('author', {}).get('displayName', '?')}] {c.get('body', '')}"
                for c in comments
            )

            # Historique de statuts via changelog
            changelog = issue.get("changelog", {})
            history_entries = changelog.get("histories", [])
            status_history: list[str] = []
            for entry in history_entries:
                for item in entry.get("items", []):
                    if item.get("field") == "status":
                        status_history.append(
                            f"{entry.get('created', '?')} : "
                            f"{item.get('fromString')} → {item.get('toString')}"
                        )

            # Liens entre tickets
            links = fields.get("issuelinks", [])
            links_text = "\n".join(
                f"{lnk.get('type', {}).get('name', '?')} : "
                f"{(lnk.get('outwardIssue') or lnk.get('inwardIssue') or {}).get('key', '?')}"
                for lnk in links
            )

            content_parts: list[str] = [description]
            if comments_text:
                content_parts.append("=== Commentaires ===\n" + comments_text)
            if status_history:
                content_parts.append(
                    "=== Historique statuts ===\n" + "\n".join(status_history)
                )
            if links_text:
                content_parts.append("=== Liens ===\n" + links_text)

            reporter_info = fields.get("reporter") or {}
            assignee_info = fields.get("assignee") or {}
            auteur = reporter_info.get("displayName") or assignee_info.get("displayName")

            return RawDocument(
                id_source=key,
                source_type="jira",
                titre=f"[{key}] {summary}",
                contenu_texte="\n\n".join(p for p in content_parts if p),
                auteur=auteur,
                date_creation=_parse_dt(fields.get("created")),
                date_modification=_parse_dt(fields.get("updated")),
                url_ou_chemin=f"{self._jira.url}/browse/{key}",
                metadonnees={
                    "key": key,
                    "status": (fields.get("status") or {}).get("name"),
                    "assignee": assignee_info.get("displayName"),
                    "nb_comments": len(comments),
                    "nb_status_changes": len(status_history),
                    "nb_links": len(links),
                },
            )
        except Exception as exc:
            logger.error("Impossible de convertir l'issue %s : %s", issue.get("key"), exc)
            return None


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    """Parse une date ISO 8601 Jira (avec timezone)."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None
