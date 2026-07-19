"""
Tests du flux d'ingestion conversationnel (sans LLM réseau) :

- extraction_schema : validation Pydantic du JSON produit par l'agent
- graph_writer : écriture Neo4j déterministe (add_nodes_and_edges_bulk mocké),
  dédoublonnage par clé métier, résolution des relations par clé locale.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

from kb_smart_metering.ingestion.extraction_schema import (
    VALID_ENTITY_TYPES,
    ExtractedEntity,
    ExtractedRelation,
    ExtractionResult,
)
from kb_smart_metering.ingestion.graph_writer import GraphWriter

_BULK_PATCH_TARGET = "kb_smart_metering.ingestion.graph_writer.add_nodes_and_edges_bulk"


# ---------------------------------------------------------------------------
# extraction_schema
# ---------------------------------------------------------------------------


class TestExtractionSchema:
    def test_type_valide_accepte(self) -> None:
        entity = ExtractedEntity(key="k1", type="Ticket", name="SMART-1")
        assert entity.type == "Ticket"

    def test_type_invalide_leve_erreur(self) -> None:
        with pytest.raises(ValidationError):
            ExtractedEntity(key="k1", type="NotAType", name="x")

    def test_tous_les_types_du_domaine_valides(self) -> None:
        for t in VALID_ENTITY_TYPES:
            ExtractedEntity(key="k", type=t, name="n")

    def test_neuf_types_exactement(self) -> None:
        assert len(VALID_ENTITY_TYPES) == 9

    def test_extraction_result_defaults_vides(self) -> None:
        result = ExtractionResult(source_ref="jira:SMART-1")
        assert result.entities == []
        assert result.relations == []

    def test_relation_champs_requis(self) -> None:
        rel = ExtractedRelation(
            source_key="a", target_key="b", name="concerne", fact="A concerne B."
        )
        assert rel.valid_at is None
        assert rel.invalid_at is None


# ---------------------------------------------------------------------------
# graph_writer — helpers
# ---------------------------------------------------------------------------


def _make_mock_driver(existing_uuid: str | None = None) -> MagicMock:
    driver = MagicMock()
    records = [{"uuid": existing_uuid}] if existing_uuid else []
    driver.execute_query = AsyncMock(return_value=(records, None, None))
    return driver


def _make_mock_embedder() -> MagicMock:
    embedder = MagicMock()
    embedder.create = AsyncMock(return_value=[0.1, 0.2, 0.3])
    return embedder


# ---------------------------------------------------------------------------
# graph_writer — GraphWriter.write
# ---------------------------------------------------------------------------


class TestGraphWriter:
    @pytest.mark.asyncio
    async def test_nouvelle_entite_creee(self) -> None:
        driver = _make_mock_driver(existing_uuid=None)
        writer = GraphWriter(driver=driver, embedder=_make_mock_embedder(), group_id="test")

        extraction = ExtractionResult(
            source_ref="jira:SMART-1",
            entities=[
                ExtractedEntity(
                    key="t1", type="Ticket", name="SMART-1", attributes={"status": "Ouvert"}
                )
            ],
        )

        with patch(_BULK_PATCH_TARGET, new=AsyncMock()) as mock_bulk:
            result = await writer.write(extraction)

        assert result.nodes_created == 1
        assert result.nodes_reused == 0
        assert result.edges_created == 0

        nodes = mock_bulk.await_args.args[3]
        assert len(nodes) == 1
        assert nodes[0].labels == ["Entity", "Ticket"]
        assert nodes[0].attributes["status"] == "Ouvert"
        assert nodes[0].attributes["source_key"] == "t1"
        assert nodes[0].attributes["source_ref"] == "jira:SMART-1"

    @pytest.mark.asyncio
    async def test_entite_existante_reutilisee_pas_dupliquee(self) -> None:
        driver = _make_mock_driver(existing_uuid="existing-uuid-123")
        writer = GraphWriter(driver=driver, embedder=_make_mock_embedder(), group_id="test")

        extraction = ExtractionResult(
            source_ref="jira:SMART-1",
            entities=[ExtractedEntity(key="t1", type="Ticket", name="SMART-1")],
        )

        with patch(_BULK_PATCH_TARGET, new=AsyncMock()) as mock_bulk:
            result = await writer.write(extraction)

        assert result.nodes_created == 0
        assert result.nodes_reused == 1
        nodes = mock_bulk.await_args.args[3]
        assert nodes[0].uuid == "existing-uuid-123"

    @pytest.mark.asyncio
    async def test_relation_resolue_par_cle_locale(self) -> None:
        driver = _make_mock_driver(existing_uuid=None)
        writer = GraphWriter(driver=driver, embedder=_make_mock_embedder(), group_id="test")

        extraction = ExtractionResult(
            source_ref="jira:SMART-1",
            entities=[
                ExtractedEntity(key="t1", type="Ticket", name="SMART-1"),
                ExtractedEntity(key="app1", type="Application", name="Unity Water"),
            ],
            relations=[
                ExtractedRelation(
                    source_key="t1",
                    target_key="app1",
                    name="concerne",
                    fact="Le ticket SMART-1 concerne Unity Water.",
                )
            ],
        )

        with patch(_BULK_PATCH_TARGET, new=AsyncMock()) as mock_bulk:
            result = await writer.write(extraction)

        assert result.edges_created == 1
        edges = mock_bulk.await_args.args[4]
        assert len(edges) == 1
        assert edges[0].source_node_uuid != edges[0].target_node_uuid
        assert edges[0].fact == "Le ticket SMART-1 concerne Unity Water."

    @pytest.mark.asyncio
    async def test_relation_cle_locale_inconnue_ignoree(self) -> None:
        driver = _make_mock_driver(existing_uuid=None)
        writer = GraphWriter(driver=driver, embedder=_make_mock_embedder(), group_id="test")

        extraction = ExtractionResult(
            source_ref="jira:SMART-1",
            entities=[ExtractedEntity(key="t1", type="Ticket", name="SMART-1")],
            relations=[
                ExtractedRelation(
                    source_key="t1", target_key="inconnu", name="concerne", fact="fact"
                )
            ],
        )

        with patch(_BULK_PATCH_TARGET, new=AsyncMock()):
            result = await writer.write(extraction)

        assert result.edges_created == 0

    @pytest.mark.asyncio
    async def test_aucune_entite_aucune_relation(self) -> None:
        driver = _make_mock_driver(existing_uuid=None)
        writer = GraphWriter(driver=driver, embedder=_make_mock_embedder(), group_id="test")

        extraction = ExtractionResult(source_ref="jira:SMART-1")

        with patch(_BULK_PATCH_TARGET, new=AsyncMock()) as mock_bulk:
            result = await writer.write(extraction)

        assert result.nodes_created == 0
        assert result.edges_created == 0
        mock_bulk.assert_awaited_once()
