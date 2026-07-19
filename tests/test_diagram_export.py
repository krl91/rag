"""
Tests de la génération de diagrammes Mermaid (revengine/diagram_export.py).

Purement déterministe, aucun mock nécessaire (pas d'appel LLM ni réseau).
"""

from kb_smart_metering.revengine.ast_extract import ClassInfo, ExtractedModule, MethodInfo
from kb_smart_metering.revengine.diagram_export import mermaid_for_module, mermaid_for_relations
from kb_smart_metering.revengine.graph_build import RelationCandidate


def _make_module(classes: list[ClassInfo]) -> ExtractedModule:
    return ExtractedModule(
        language="python",
        file_path="/repo/service.py",
        module_name="service",
        classes=classes,
    )


def _make_class(
    name: str,
    events_published: list[str] | None = None,
    events_subscribed: list[str] | None = None,
    outgoing_components: list[str] | None = None,
) -> ClassInfo:
    return ClassInfo(
        name=name,
        kind="class",
        line_start=1,
        line_end=10,
        methods=[MethodInfo(name="m", line_start=1, line_end=2)],
        events_published=events_published or [],
        events_subscribed=events_subscribed or [],
        outgoing_components=outgoing_components or [],
    )


class TestMermaidForModule:
    def test_module_sans_contenu_retourne_chaine_vide(self) -> None:
        module = _make_module([_make_class("Vide")])
        assert mermaid_for_module(module) == ""

    def test_evenement_publie(self) -> None:
        module = _make_module([_make_class("ExportService", events_published=["ExportEvent"])])
        diagram = mermaid_for_module(module)

        assert diagram.startswith("flowchart LR")
        assert 'c_ExportService["ExportService"]' in diagram
        assert 'e_ExportEvent{{"ExportEvent"}}' in diagram
        assert "c_ExportService -->|publie| e_ExportEvent" in diagram

    def test_evenement_consomme(self) -> None:
        module = _make_module(
            [_make_class("BillingListener", events_subscribed=["ExportEvent"])]
        )
        diagram = mermaid_for_module(module)

        assert "e_ExportEvent -->|consommé par| c_BillingListener" in diagram

    def test_appel_sortant(self) -> None:
        module = _make_module(
            [_make_class("ExportService", outgoing_components=["MDMClient"])]
        )
        diagram = mermaid_for_module(module)

        assert 'd_MDMClient(["MDMClient"])' in diagram
        assert "c_ExportService -.->|appelle| d_MDMClient" in diagram

    def test_noeuds_dedupliques(self) -> None:
        """Le même événement référencé par deux classes ne doit apparaître qu'une fois."""
        module = _make_module(
            [
                _make_class("A", events_published=["SharedEvent"]),
                _make_class("B", events_subscribed=["SharedEvent"]),
            ]
        )
        diagram = mermaid_for_module(module)

        assert diagram.count('e_SharedEvent{{"SharedEvent"}}') == 1

    def test_id_stable_pour_noms_avec_caracteres_speciaux(self) -> None:
        module = _make_module(
            [_make_class("Export-Service.v2", events_published=["Meter.Reading#Event"])]
        )
        diagram = mermaid_for_module(module)

        # Pas de caractères non-alphanumériques dans les identifiants des
        # déclarations de nœuds (lignes contenant un label entre guillemets,
        # par opposition aux lignes d'arêtes qui référencent juste l'id).
        for line in diagram.splitlines():
            stripped = line.strip()
            if '"' not in stripped:
                continue
            node_id = stripped.split("[")[0].split("{")[0].strip()
            assert node_id.replace("_", "").isalnum(), node_id


class TestMermaidForRelations:
    def test_liste_vide_retourne_chaine_vide(self) -> None:
        assert mermaid_for_relations([]) == ""

    def test_relation_publie(self) -> None:
        relations = [
            RelationCandidate(
                source_component="ExportService",
                target="ExportEvent",
                kind="publie",
                source_file="/repo/service.py",
                line=1,
            )
        ]
        diagram = mermaid_for_relations(relations)

        assert 'c_ExportService["ExportService"]' in diagram
        assert 'e_ExportEvent{{"ExportEvent"}}' in diagram
        assert "c_ExportService -->|publie| e_ExportEvent" in diagram

    def test_relation_appelle_utilise_noeuds_rectangle_et_fleche_pointillee(self) -> None:
        relations = [
            RelationCandidate(
                source_component="ExportService",
                target="MDMClient",
                kind="appelle",
                source_file="/repo/service.py",
                line=1,
                confidence=0.5,
            )
        ]
        diagram = mermaid_for_relations(relations)

        assert 'c_MDMClient["MDMClient"]' in diagram  # composant, pas événement
        assert "c_ExportService -.->|appelle| c_MDMClient" in diagram

    def test_plusieurs_relations_meme_composant_noeud_unique(self) -> None:
        relations = [
            RelationCandidate(
                source_component="ExportService", target="ExportEvent",
                kind="publie", source_file="f", line=1,
            ),
            RelationCandidate(
                source_component="ExportService", target="MDMClient",
                kind="appelle", source_file="f", line=2, confidence=0.5,
            ),
        ]
        diagram = mermaid_for_relations(relations)

        assert diagram.count('c_ExportService["ExportService"]') == 1
