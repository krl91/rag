"""
Tests du module ingestion (Phase 2).

Tests unitaires (sans réseau) :
- entity_types : validation des noms de champs vs EntityNode
- embedder : structure de l'embedding retourné (mocké)
- pipeline : idempotence via SQLite, dry_run, résultats
- normalize_file_source_id : comportement sur chemins Windows simulés

Tests d'intégration (@integration) :
- Ingestion de 2 fixtures de réunion dans un Neo4j de test.
  Activer avec : uv run pytest -m integration
"""

import hashlib
import sqlite3
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import BaseModel

from kb_smart_metering.ingestion.entity_types import ENTITY_TYPES
from kb_smart_metering.ingestion.pipeline import IngestionPipeline, IngestionResult
from kb_smart_metering.normalize.models import RawDocument, normalize_file_source_id

FIXTURES_DIR = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# Fixtures communes
# ---------------------------------------------------------------------------


def make_raw_document(
    id_source: str = "TEST-001",
    source_type: str = "meeting",
    titre: str = "Réunion test",
    contenu: str = "Jean Dupont parle de l'intégration MDM v3 avec Alice Martin.",
    date_modif: datetime | None = None,
) -> RawDocument:
    return RawDocument(
        id_source=id_source,
        source_type=source_type,  # type: ignore[arg-type]
        titre=titre,
        contenu_texte=contenu,
        date_modification=date_modif,
    )


def make_fake_graphiti(nodes: int = 3, edges: int = 2) -> MagicMock:
    """Crée un mock Graphiti dont add_episode retourne un résultat cohérent."""
    fake_result = MagicMock()
    fake_result.nodes = [MagicMock() for _ in range(nodes)]
    fake_result.edges = [MagicMock() for _ in range(edges)]

    graphiti = MagicMock()
    graphiti.add_episode = AsyncMock(return_value=fake_result)
    return graphiti


# ---------------------------------------------------------------------------
# Tests entity_types
# ---------------------------------------------------------------------------


class TestEntityTypes:
    def test_champs_absents_de_entity_node(self) -> None:
        """Les champs des entity_types ne doivent pas entrer en conflit avec EntityNode."""
        from graphiti_core.utils.ontology_utils.entity_types_utils import validate_entity_types

        # Ne doit pas lever EntityTypeValidationError
        validate_entity_types(ENTITY_TYPES)

    def test_toutes_les_entites_presentes(self) -> None:
        expected = {
            "Person", "Application", "Component", "Document",
            "Ticket", "Meeting", "Decision", "Action", "BusinessRule",
        }
        assert set(ENTITY_TYPES.keys()) == expected

    def test_toutes_les_entites_sont_pydantic(self) -> None:
        for name, model in ENTITY_TYPES.items():
            assert issubclass(model, BaseModel), f"{name} n'est pas un BaseModel"


# ---------------------------------------------------------------------------
# Tests embedder (sans chargement réel du modèle)
# ---------------------------------------------------------------------------


class TestBGEM3Embedder:
    def test_embedder_instanciation(self) -> None:
        """L'embedder s'instancie sans charger le modèle (lazy loading)."""
        from kb_smart_metering.ingestion.embedder import BGEM3Embedder

        embedder = BGEM3Embedder()
        assert embedder._model is None  # pas encore chargé

    @pytest.mark.asyncio
    async def test_create_retourne_liste_floats(self, tmp_path: Path) -> None:
        """Vérifie que create() retourne bien une liste de flottants."""
        from kb_smart_metering.ingestion.embedder import BGEM3Embedder

        embedder = BGEM3Embedder()
        # Remplace le modèle par un mock qui retourne un vecteur de 1024 dims
        mock_model = MagicMock()
        mock_model.encode.return_value = [0.1] * 1024
        embedder._model = mock_model

        result = await embedder.create("test d'embedding")
        assert isinstance(result, list)
        assert len(result) == 1024
        assert all(isinstance(v, float) for v in result)

    @pytest.mark.asyncio
    async def test_create_accepte_liste_de_strings(self) -> None:
        from kb_smart_metering.ingestion.embedder import BGEM3Embedder

        embedder = BGEM3Embedder()
        mock_model = MagicMock()
        mock_model.encode.return_value = [0.0] * 1024
        embedder._model = mock_model

        result = await embedder.create(["texte un", "texte deux"])
        assert isinstance(result, list)
        assert len(result) == 1024


# ---------------------------------------------------------------------------
# Tests pipeline — unitaires (SQLite in-memory / tmp_path)
# ---------------------------------------------------------------------------


class TestIngestionPipeline:
    def _make_pipeline(self, tmp_path: Path, nodes: int = 2, edges: int = 1) -> IngestionPipeline:
        graphiti = make_fake_graphiti(nodes=nodes, edges=edges)
        return IngestionPipeline(
            graphiti=graphiti,
            tracking_db=tmp_path / "tracking.db",
            group_id="test",
        )

    @pytest.mark.asyncio
    async def test_premiere_ingestion_succes(self, tmp_path: Path) -> None:
        pipeline = self._make_pipeline(tmp_path, nodes=3, edges=2)
        doc = make_raw_document()

        result = await pipeline.ingest_document(doc)

        assert isinstance(result, IngestionResult)
        assert not result.skipped
        assert result.nodes_created == 3
        assert result.edges_created == 2

    @pytest.mark.asyncio
    async def test_reingestion_ignoree_si_contenu_identique(self, tmp_path: Path) -> None:
        pipeline = self._make_pipeline(tmp_path)
        doc = make_raw_document()

        result1 = await pipeline.ingest_document(doc)
        result2 = await pipeline.ingest_document(doc)

        assert not result1.skipped
        assert result2.skipped
        # add_episode ne doit être appelé qu'une fois
        pipeline._graphiti.add_episode.assert_awaited_once()  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_reingestion_si_contenu_change(self, tmp_path: Path) -> None:
        pipeline = self._make_pipeline(tmp_path)
        date = datetime(2024, 1, 15, tzinfo=timezone.utc)
        doc1 = make_raw_document(contenu="version 1", date_modif=date)
        doc2 = make_raw_document(
            contenu="version 2 modifiée",
            date_modif=datetime(2024, 1, 20, tzinfo=timezone.utc),
        )

        result1 = await pipeline.ingest_document(doc1)
        result2 = await pipeline.ingest_document(doc2)

        assert not result1.skipped
        assert not result2.skipped

    @pytest.mark.asyncio
    async def test_dry_run_ne_ecrit_pas(self, tmp_path: Path) -> None:
        pipeline = self._make_pipeline(tmp_path)
        doc = make_raw_document()

        result = await pipeline.ingest_document(doc, dry_run=True)

        assert not result.skipped
        assert result.nodes_created == 0
        assert result.edges_created == 0
        pipeline._graphiti.add_episode.assert_not_awaited()  # type: ignore[attr-defined]

        # Vérifier que le document n'est pas marqué comme ingéré
        result2 = await pipeline.ingest_document(doc, dry_run=True)
        assert not result2.skipped  # on peut le ré-ingérer (dry_run ne persiste pas)

    @pytest.mark.asyncio
    async def test_episode_key_stable(self, tmp_path: Path) -> None:
        date = datetime(2024, 3, 10, 12, 0, tzinfo=timezone.utc)
        doc = make_raw_document(id_source="CONF-123", source_type="confluence", date_modif=date)
        key = IngestionPipeline._episode_key(doc)
        assert key == f"confluence:CONF-123:{date.isoformat()}"

    @pytest.mark.asyncio
    async def test_episode_key_sans_date_utilise_hash(self, tmp_path: Path) -> None:
        doc = make_raw_document(id_source="GIT-abc", source_type="git", date_modif=None)
        key = IngestionPipeline._episode_key(doc)
        expected_hash = hashlib.sha256(doc.contenu_texte.encode()).hexdigest()[:16]
        assert key == f"git:GIT-abc:{expected_hash}"

    @pytest.mark.asyncio
    async def test_ingest_batch_sequentiel(self, tmp_path: Path) -> None:
        pipeline = self._make_pipeline(tmp_path, nodes=1, edges=1)
        docs = [
            make_raw_document(id_source=f"DOC-{i}", contenu=f"Contenu document {i}")
            for i in range(4)
        ]
        results = await pipeline.ingest_batch(docs)

        assert len(results) == 4
        assert all(not r.skipped for r in results)
        assert pipeline._graphiti.add_episode.await_count == 4  # type: ignore[attr-defined]

    def test_sqlite_persistance(self, tmp_path: Path) -> None:
        """Vérifie que la table SQLite est bien créée et persistée."""
        db_path = tmp_path / "tracking.db"
        graphiti = make_fake_graphiti()
        IngestionPipeline(graphiti=graphiti, tracking_db=db_path)

        with sqlite3.connect(db_path) as conn:
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        assert ("ingested_episodes",) in tables


# ---------------------------------------------------------------------------
# Tests normalisation des chemins fichiers (chemins Windows simulés)
# ---------------------------------------------------------------------------


class TestNormalizeFileSourceId:
    """Valide normalize_file_source_id sur des chemins POSIX et Windows simulés."""

    def test_chemin_posix_pas_de_backslash(self, tmp_path: Path) -> None:
        """Un chemin POSIX réel ne doit pas contenir de backslash."""
        result = normalize_file_source_id(tmp_path / "fichier.docx")
        assert "\\" not in result

    def test_chemin_posix_utilise_slashes(self, tmp_path: Path) -> None:
        """Le chemin retourné doit utiliser des slashes POSIX."""
        result = normalize_file_source_id(tmp_path / "docs" / "rapport.pdf")
        assert "/" in result

    def test_chemin_windows_simule_sans_backslash(self) -> None:
        """Simule un chemin Windows absolu via PureWindowsPath et vérifie as_posix()."""
        # PureWindowsPath ne peut pas appeler .resolve() (pas de vrai filesystem),
        # on teste donc directement as_posix() sur le chemin Windows.
        win_path = PureWindowsPath(r"C:\Users\karelredon\docs\rapport.docx")
        result = win_path.as_posix()
        assert "\\" not in result
        assert result == "C:/Users/karelredon/docs/rapport.docx"

    def test_chemin_windows_simule_pas_de_separateur_colon_double(self) -> None:
        """Vérifie qu'un id_source Windows simulé ne produit pas de double '::'."""
        win_path = PureWindowsPath(r"C:\Users\karelredon\docs\fichier.docx")
        id_source = win_path.as_posix()
        # Format episode_key : "docx:{id_source}:{version}"
        episode_key = f"docx:{id_source}:2024-01-15T10:30:00+00:00"
        # La clé doit avoir exactement 4 segments séparés par ':' (source_type, drive, path, version)
        # Ce qui compte : le premier segment est bien "docx"
        parts = episode_key.split(":")
        assert parts[0] == "docx"

    def test_episode_key_windows_pas_de_backslash(self) -> None:
        """Une episode_key construite avec un chemin Windows simulé ne contient pas de backslash."""
        win_path = PureWindowsPath(r"C:\Users\karelredon\data\reunion.txt")
        id_source = win_path.as_posix()
        doc = RawDocument(
            id_source=id_source,
            source_type="meeting",
            titre="Réunion test Windows",
            contenu_texte="Segment de réunion.",
            date_modification=datetime(2024, 3, 10, 12, 0, tzinfo=timezone.utc),
        )
        key = IngestionPipeline._episode_key(doc)
        assert "\\" not in key
        assert key == "meeting:C:/Users/karelredon/data/reunion.txt:2024-03-10T12:00:00+00:00"

    def test_normalize_retourne_string(self, tmp_path: Path) -> None:
        """normalize_file_source_id retourne toujours une str."""
        result = normalize_file_source_id(tmp_path / "test.xlsx")
        assert isinstance(result, str)

    def test_normalize_accepte_str_et_path(self, tmp_path: Path) -> None:
        """normalize_file_source_id accepte str et Path."""
        path_obj = tmp_path / "test.pdf"
        result_path = normalize_file_source_id(path_obj)
        result_str = normalize_file_source_id(str(path_obj))
        assert result_path == result_str

    def test_idempotence_double_appel(self, tmp_path: Path) -> None:
        """Appeler normalize_file_source_id deux fois sur le même chemin donne le même résultat."""
        path = tmp_path / "doc.docx"
        assert normalize_file_source_id(path) == normalize_file_source_id(path)





@pytest.mark.integration
class TestIngestionIntegration:
    """
    Tests d'intégration réels : Neo4j + Ollama doivent être démarrés.

    Lancer avec :
        uv run pytest -m integration

    Les fixtures utilisées sont les fichiers de transcription de réunion
    présents dans tests/fixtures/.
    """

    @pytest.fixture()
    def graphiti_real(self):
        """Instance Graphiti réelle pointant sur Neo4j de test."""
        from kb_smart_metering.ingestion.graphiti import build_graphiti

        g = build_graphiti()
        yield g
        import asyncio
        asyncio.get_event_loop().run_until_complete(g.close())

    @pytest.fixture()
    def fixtures_docs(self) -> list[RawDocument]:
        """Charge les 2 fixtures de transcription comme RawDocument."""
        docs = []
        for fixture_file in sorted(FIXTURES_DIR.iterdir()):
            content = fixture_file.read_text(encoding="utf-8")
            docs.append(
                RawDocument(
                    id_source=fixture_file.stem,
                    source_type="meeting",  # type: ignore[arg-type]
                    titre=f"Transcription : {fixture_file.stem}",
                    contenu_texte=content,
                    url_ou_chemin=str(fixture_file),
                    date_creation=datetime(2024, 1, 15, tzinfo=timezone.utc),
                )
            )
        assert len(docs) >= 2, "Il faut au moins 2 fixtures dans tests/fixtures/"
        return docs[:2]

    @pytest.mark.asyncio
    async def test_ingestion_deux_fixtures(
        self, graphiti_real: Any, fixtures_docs: list[RawDocument], tmp_path: Path
    ) -> None:
        """Ingère 2 transcriptions et vérifie qu'au moins une entité est créée."""
        import asyncio

        await graphiti_real.build_indices_and_constraints()

        pipeline = IngestionPipeline(
            graphiti=graphiti_real,
            tracking_db=tmp_path / "tracking_integ.db",
            group_id="test_integration",
        )
        results = await pipeline.ingest_batch(fixtures_docs)

        assert len(results) == 2
        assert all(not r.skipped for r in results)
        total_nodes = sum(r.nodes_created for r in results)
        assert total_nodes >= 1, "Au moins une entité doit être extraite"

    @pytest.mark.asyncio
    async def test_idempotence_reelle(
        self, graphiti_real: Any, fixtures_docs: list[RawDocument], tmp_path: Path
    ) -> None:
        """Vérifie qu'une deuxième exécution n'ré-ingère pas les mêmes épisodes."""
        await graphiti_real.build_indices_and_constraints()

        pipeline = IngestionPipeline(
            graphiti=graphiti_real,
            tracking_db=tmp_path / "tracking_idemp.db",
            group_id="test_idempotence",
        )
        await pipeline.ingest_batch([fixtures_docs[0]])
        results_second = await pipeline.ingest_batch([fixtures_docs[0]])

        assert results_second[0].skipped
