"""
Pipeline d'ingestion : RawDocument → épisodes Graphiti.

Règles de découpage en épisodes :
- 1 ticket Jira     → 1 épisode
- 1 page Confluence → 1 épisode (une par version)
- 1 réunion         → 1 épisode
- 1 fichier         → 1 épisode

Idempotence : une table SQLite locale (data/ingestion_tracking.db)
conserve la clé et le hash de contenu de chaque épisode déjà ingéré.
Un épisode n'est ré-ingéré que si son contenu a changé.
"""

import hashlib
import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from graphiti_core.graphiti import Graphiti
from graphiti_core.nodes import EpisodeType

from kb_smart_metering.ingestion.entity_types import ENTITY_TYPES
from kb_smart_metering.normalize.models import RawDocument

logger = logging.getLogger(__name__)

# Correspondance source → EpisodeType Graphiti
_SOURCE_TO_EPISODE_TYPE: dict[str, EpisodeType] = {
    "jira": EpisodeType.text,
    "confluence": EpisodeType.text,
    "git": EpisodeType.text,
    "docx": EpisodeType.text,
    "xlsx": EpisodeType.text,
    "pdf": EpisodeType.text,
    "meeting": EpisodeType.text,
    "obsidian": EpisodeType.text,
}

_DEFAULT_TRACKING_DB = Path("data") / "ingestion_tracking.db"


@dataclass
class IngestionResult:
    """Résultat de l'ingestion d'un épisode."""

    episode_key: str
    skipped: bool
    nodes_created: int = 0
    edges_created: int = 0

    def __str__(self) -> str:
        if self.skipped:
            return f"[ignoré] {self.episode_key}"
        return (
            f"[ingéré] {self.episode_key} "
            f"— {self.nodes_created} entités, {self.edges_created} relations"
        )


class IngestionPipeline:
    """
    Pipeline principal d'ingestion RawDocument → Graphiti.

    Paramètres
    ----------
    graphiti : Graphiti
        Instance Graphiti configurée (LLM + embedder + Neo4j).
    tracking_db : Path | None
        Chemin de la base SQLite de suivi. Par défaut : data/ingestion_tracking.db.
    group_id : str
        Partition du graphe Graphiti (= tenant). Défaut : "smart_metering".
    """

    def __init__(
        self,
        graphiti: Graphiti,
        tracking_db: Path | None = None,
        group_id: str = "smart_metering",
    ) -> None:
        self._graphiti = graphiti
        self._group_id = group_id
        self._db_path = tracking_db or _DEFAULT_TRACKING_DB
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    # ------------------------------------------------------------------
    # SQLite — initialisation et accès
    # ------------------------------------------------------------------

    def _init_db(self) -> None:
        """Crée la table de suivi si elle n'existe pas encore."""
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS ingested_episodes (
                    episode_key  TEXT PRIMARY KEY,
                    content_hash TEXT NOT NULL,
                    ingested_at  TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def _is_already_ingested(self, episode_key: str, content_hash: str) -> bool:
        """Retourne True si l'épisode a déjà été ingéré avec le même contenu."""
        with sqlite3.connect(self._db_path) as conn:
            row = conn.execute(
                "SELECT content_hash FROM ingested_episodes WHERE episode_key = ?",
                (episode_key,),
            ).fetchone()
        if row is None:
            return False
        return row[0] == content_hash

    def _mark_ingested(self, episode_key: str, content_hash: str) -> None:
        """Enregistre l'épisode comme ingéré dans la table de suivi."""
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO ingested_episodes
                    (episode_key, content_hash, ingested_at)
                VALUES (?, ?, ?)
                """,
                (episode_key, content_hash, now),
            )
            conn.commit()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _episode_key(doc: RawDocument) -> str:
        """
        Clé stable et unique par épisode.

        Format : ``{source_type}:{id_source}:{version}``
        La version est la date de modification ISO si disponible,
        sinon les 16 premiers caractères du SHA-256 du contenu.
        """
        if doc.date_modification:
            version = doc.date_modification.isoformat()
        else:
            version = hashlib.sha256(doc.contenu_texte.encode()).hexdigest()[:16]
        return f"{doc.source_type}:{doc.id_source}:{version}"

    @staticmethod
    def _content_hash(doc: RawDocument) -> str:
        return hashlib.sha256(doc.contenu_texte.encode()).hexdigest()

    # ------------------------------------------------------------------
    # Ingestion
    # ------------------------------------------------------------------

    async def ingest_document(
        self,
        doc: RawDocument,
        dry_run: bool = False,
    ) -> IngestionResult:
        """
        Ingère un RawDocument comme épisode Graphiti.

        Paramètres
        ----------
        doc : RawDocument
            Document normalisé produit par un extracteur.
        dry_run : bool
            Si True, simule l'ingestion sans écrire dans Neo4j ni SQLite.

        Retourne
        --------
        IngestionResult
        """
        episode_key = self._episode_key(doc)
        content_hash = self._content_hash(doc)

        if self._is_already_ingested(episode_key, content_hash):
            logger.info("Episode déjà ingéré (ignoré) : %s", episode_key)
            return IngestionResult(episode_key=episode_key, skipped=True)

        reference_time: datetime = (
            doc.date_modification
            or doc.date_creation
            or datetime.now(timezone.utc)
        )
        episode_type = _SOURCE_TO_EPISODE_TYPE.get(doc.source_type, EpisodeType.text)

        source_description = f"{doc.source_type}:{doc.id_source}"
        if doc.url_ou_chemin:
            source_description += f" ({doc.url_ou_chemin})"

        logger.info(
            "Ingestion épisode %s [dry_run=%s, type=%s]",
            episode_key,
            dry_run,
            episode_type.value,
        )

        if dry_run:
            return IngestionResult(
                episode_key=episode_key,
                skipped=False,
                nodes_created=0,
                edges_created=0,
            )

        result = await self._graphiti.add_episode(
            name=doc.titre,
            episode_body=doc.contenu_texte,
            source_description=source_description,
            reference_time=reference_time,
            source=episode_type,
            group_id=self._group_id,
            entity_types=ENTITY_TYPES,
        )

        nodes_created = len(result.nodes)
        edges_created = len(result.edges)

        logger.info(
            "Episode ingéré %s → %d entités, %d relations",
            episode_key,
            nodes_created,
            edges_created,
        )

        self._mark_ingested(episode_key, content_hash)

        return IngestionResult(
            episode_key=episode_key,
            skipped=False,
            nodes_created=nodes_created,
            edges_created=edges_created,
        )

    async def ingest_batch(
        self,
        docs: list[RawDocument],
        dry_run: bool = False,
    ) -> list[IngestionResult]:
        """
        Ingère une liste de RawDocument de façon séquentielle.

        Graphiti exige une ingestion séquentielle (non concurrente) pour
        maintenir la cohérence du graphe temporel.

        Paramètres
        ----------
        docs : list[RawDocument]
            Documents à ingérer dans l'ordre.
        dry_run : bool
            Si True, simule sans écriture.

        Retourne
        --------
        list[IngestionResult]
        """
        results: list[IngestionResult] = []
        for doc in docs:
            result = await self.ingest_document(doc, dry_run=dry_run)
            results.append(result)

        total_nodes = sum(r.nodes_created for r in results)
        total_edges = sum(r.edges_created for r in results)
        skipped = sum(1 for r in results if r.skipped)

        logger.info(
            "Batch terminé : %d épisodes traités (%d ignorés), "
            "%d entités créées, %d relations créées",
            len(results),
            skipped,
            total_nodes,
            total_edges,
        )
        return results
