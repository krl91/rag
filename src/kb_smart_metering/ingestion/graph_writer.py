"""
Écriture déterministe du graphe Neo4j à partir d'une ExtractionResult.

Remplace Graphiti.add_episode() / add_triplet(), qui appellent tous deux en
interne resolve_extracted_nodes()/resolve_extracted_edge() → self.llm_client
(vérifié en lisant graphiti_core.graphiti — aucune des 3 méthodes d'écriture
publiques de Graphiti ne fonctionne sans endpoint LLM réseau joignable).

Ici, la déduplication (idempotence) se fait par clé métier stable fournie
par l'agent (ExtractedEntity.key, ex: "SMART-74743"), pas par résolution
floue LLM : c'est l'agent qui, en amont dans la conversation, a déjà
reconnu que deux mentions désignent la même entité et leur a donné la même
clé. Python se contente d'un upsert déterministe via add_nodes_and_edges_bulk
(utilitaire public de graphiti-core, sans llm_client).
"""

import logging
from dataclasses import dataclass
from uuid import uuid4

from graphiti_core.driver.driver import GraphDriver
from graphiti_core.edges import EntityEdge
from graphiti_core.embedder.client import EmbedderClient
from graphiti_core.nodes import EntityNode
from graphiti_core.utils.bulk_utils import add_nodes_and_edges_bulk
from graphiti_core.utils.datetime_utils import utc_now

from kb_smart_metering.ingestion.extraction_schema import ExtractionResult

logger = logging.getLogger(__name__)


@dataclass
class WriteResult:
    """Résultat de l'écriture d'une ExtractionResult dans Neo4j."""

    nodes_created: int
    nodes_reused: int
    edges_created: int


class GraphWriter:
    """
    Écrit une ExtractionResult dans Neo4j, sans aucun appel LLM.

    Paramètres
    ----------
    driver : GraphDriver
        Driver Neo4j de graphiti-core (construit sans llm_client).
    embedder : EmbedderClient
        Embedder local (BGEM3Embedder) pour les name_embedding / fact_embedding.
    group_id : str
        Partition du graphe (= tenant), cohérente avec le reste du pipeline.
    """

    def __init__(
        self,
        driver: GraphDriver,
        embedder: EmbedderClient,
        group_id: str = "smart_metering",
    ) -> None:
        self._driver = driver
        self._embedder = embedder
        self._group_id = group_id

    async def _find_existing_uuid(self, entity_type: str, business_key: str) -> str | None:
        """Cherche un nœud déjà écrit portant la même clé métier (idempotence)."""
        # NB : EntityNode.attributes est aplati en propriétés de nœud de premier
        # niveau par graphiti-core (voir add_nodes_and_edges_bulk_tx / EntityNode.save) —
        # ce n'est PAS une map imbriquée. D'où n.source_key et non n.attributes.source_key.
        records, _, _ = await self._driver.execute_query(
            """
            MATCH (n:Entity)
            WHERE $type IN labels(n)
              AND n.group_id = $group_id
              AND n.source_key = $business_key
            RETURN n.uuid AS uuid
            LIMIT 1
            """,
            type=entity_type,
            group_id=self._group_id,
            business_key=business_key,
            routing_="r",
        )
        return records[0]["uuid"] if records else None

    async def write(self, extraction: ExtractionResult) -> WriteResult:
        """Écrit les entités et relations d'une ExtractionResult dans Neo4j."""
        key_to_uuid: dict[str, str] = {}
        nodes: list[EntityNode] = []
        nodes_reused = 0

        for entity in extraction.entities:
            existing_uuid = await self._find_existing_uuid(entity.type, entity.key)

            attributes = dict(entity.attributes)
            attributes["source_key"] = entity.key
            attributes["source_ref"] = extraction.source_ref

            node = EntityNode(
                uuid=existing_uuid or str(uuid4()),
                name=entity.name,
                group_id=self._group_id,
                labels=["Entity", entity.type],
                summary=entity.summary,
                attributes=attributes,
            )
            await node.generate_name_embedding(self._embedder)
            nodes.append(node)
            key_to_uuid[entity.key] = node.uuid
            if existing_uuid:
                nodes_reused += 1

        edges: list[EntityEdge] = []
        for relation in extraction.relations:
            source_uuid = key_to_uuid.get(relation.source_key)
            target_uuid = key_to_uuid.get(relation.target_key)
            if source_uuid is None or target_uuid is None:
                logger.warning(
                    "Relation ignorée — clé locale inconnue dans ce batch : %s -> %s",
                    relation.source_key,
                    relation.target_key,
                )
                continue

            edge = EntityEdge(
                group_id=self._group_id,
                source_node_uuid=source_uuid,
                target_node_uuid=target_uuid,
                created_at=utc_now(),
                name=relation.name,
                fact=relation.fact,
                valid_at=relation.valid_at,
                invalid_at=relation.invalid_at,
                episodes=[extraction.source_ref],
            )
            await edge.generate_embedding(self._embedder)
            edges.append(edge)

        await add_nodes_and_edges_bulk(self._driver, [], [], nodes, edges, self._embedder)

        logger.info(
            "Écriture terminée pour %s — %d nœuds (%d réutilisés), %d relations",
            extraction.source_ref,
            len(nodes),
            nodes_reused,
            len(edges),
        )
        return WriteResult(
            nodes_created=len(nodes) - nodes_reused,
            nodes_reused=nodes_reused,
            edges_created=len(edges),
        )
