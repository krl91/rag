"""
Tests unitaires pour src/kb_smart_metering/revengine/.

Couverture :
  - ast_extract : extraction Java, Python, C# (heuristiques événements)
  - graph_build : construction RawDocument + relations candidates
  - docgen      : rendu Markdown + appel LLM mocké
"""

import json
import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Sauter tout le module si tree-sitter-language-pack n'est pas installé
# (dépendance optionnelle : uv sync --extra revengine)
pytest.importorskip("tree_sitter_language_pack")

from kb_smart_metering.revengine.ast_extract import (
    ASTExtractor,
    ClassInfo,
    ExtractedModule,
    Language,
    MethodInfo,
    _classify_call,
    _is_event_type,
)
from kb_smart_metering.revengine.docgen import DocGenerator, ModuleDoc, render_markdown
from kb_smart_metering.revengine.graph_build import GraphBuilder, RelationCandidate

# ---------------------------------------------------------------------------
# Fixtures communes
# ---------------------------------------------------------------------------


@pytest.fixture()
def tmp_java_file(tmp_path: Path) -> Path:
    """Fichier Java minimal avec classe, méthode, événement publié."""
    src = tmp_path / "ExportService.java"
    src.write_text(
        textwrap.dedent(
            """\
            package com.smartmetering.export;

            public class ExportService {
                private EventBus eventBus;

                public void export(MeterData data) {
                    eventBus.publish(new ExportCompletedEvent(data));
                }
            }

            public interface IExportHandler {
                void handle(ExportCompletedEvent event);
            }
            """
        ),
        encoding="utf-8",
    )
    return src


@pytest.fixture()
def tmp_python_file(tmp_path: Path) -> Path:
    """Fichier Python minimal avec classe, méthode, événement publié."""
    src = tmp_path / "meter_reader.py"
    src.write_text(
        textwrap.dedent(
            """\
            class MeterReaderService:
                def read(self, meter_id):
                    self.bus.publish(ReadingCompletedEvent(meter_id))

                def subscribe_alerts(self):
                    self.bus.subscribe(AlertEvent)
            """
        ),
        encoding="utf-8",
    )
    return src


@pytest.fixture()
def tmp_csharp_file(tmp_path: Path) -> Path:
    """Fichier C# minimal avec classe, événement C# déclaré et publication."""
    src = tmp_path / "BillingService.cs"
    src.write_text(
        textwrap.dedent(
            """\
            namespace SmartMetering.Billing {
                public class BillingService {
                    public event EventHandler BillingCompleted;
                    private IInvoiceRepository repository;

                    public void ProcessBill(BillData data) {
                        repository.Save(data);
                        eventBus.Publish(new BillGeneratedEvent(data));
                    }
                }

                public interface IBillingHandler {
                    void Handle(BillGeneratedEvent e);
                }
            }
            """
        ),
        encoding="utf-8",
    )
    return src


@pytest.fixture()
def sample_module() -> ExtractedModule:
    """Module extrait factice pour les tests graph_build et docgen."""
    return ExtractedModule(
        language="java",
        file_path="/project/src/ExportService.java",
        module_name="ExportService",
        package="com.smartmetering.export",
        classes=[
            ClassInfo(
                name="ExportService",
                kind="class",
                line_start=3,
                line_end=10,
                methods=[
                    MethodInfo(
                        name="export",
                        line_start=6,
                        line_end=9,
                        outgoing_calls=["publish"],
                        events_published=["ExportCompletedEvent"],
                        events_subscribed=[],
                    )
                ],
                events_published=["ExportCompletedEvent"],
                events_subscribed=[],
                data_models=[],
                outgoing_components=["EventBus", "MeterData"],
            ),
            ClassInfo(
                name="IExportHandler",
                kind="interface",
                line_start=12,
                line_end=14,
                methods=[
                    MethodInfo(
                        name="handle",
                        line_start=13,
                        line_end=13,
                        outgoing_calls=[],
                        events_subscribed=[],
                        events_published=[],
                    )
                ],
                events_published=[],
                events_subscribed=[],
                data_models=[],
            ),
        ],
        raw_source_excerpt="package com.smartmetering.export;\n",
    )


# ---------------------------------------------------------------------------
# Tests des heuristiques
# ---------------------------------------------------------------------------


class TestHeuristics:
    """Tests des fonctions heuristiques de détection d'événements."""

    @pytest.mark.parametrize(
        "name,expected",
        [
            ("ExportCompletedEvent", True),
            ("ReadingEvent", True),
            ("MeterData", False),
            ("EventBus", False),
            ("MyServiceEvent", True),
        ],
    )
    def test_is_event_type(self, name: str, expected: bool) -> None:
        assert _is_event_type(name) is expected

    @pytest.mark.parametrize(
        "method,expected",
        [
            ("publish", "publish"),
            ("emit", "publish"),
            ("dispatch", "publish"),
            ("subscribe", "subscribe"),
            ("consume", "subscribe"),
            ("listen", "subscribe"),
            ("addListener", "subscribe"),
            ("fetchData", None),
            ("save", None),
        ],
    )
    def test_classify_call(self, method: str, expected: str | None) -> None:
        assert _classify_call(method) == expected


# ---------------------------------------------------------------------------
# Tests d'extraction AST — Java
# ---------------------------------------------------------------------------


class TestJavaExtractor:
    """Tests de l'extracteur Java via tree-sitter."""

    def test_extract_file_returns_module(self, tmp_java_file: Path) -> None:
        extractor = ASTExtractor(Language.JAVA)
        module = extractor.extract_file(tmp_java_file)

        assert module is not None
        assert module.language == "java"
        assert module.module_name == "ExportService"

    def test_extract_detects_classes(self, tmp_java_file: Path) -> None:
        extractor = ASTExtractor(Language.JAVA)
        module = extractor.extract_file(tmp_java_file)

        assert module is not None
        class_names = [c.name for c in module.classes]
        assert "ExportService" in class_names

    def test_extract_detects_interface(self, tmp_java_file: Path) -> None:
        extractor = ASTExtractor(Language.JAVA)
        module = extractor.extract_file(tmp_java_file)

        assert module is not None
        kinds = {c.name: c.kind for c in module.classes}
        assert kinds.get("IExportHandler") == "interface"

    def test_extract_detects_published_event(self, tmp_java_file: Path) -> None:
        extractor = ASTExtractor(Language.JAVA)
        module = extractor.extract_file(tmp_java_file)

        assert module is not None
        export_class = next(c for c in module.classes if c.name == "ExportService")
        assert "ExportCompletedEvent" in export_class.events_published

    def test_extract_detects_outgoing_component(self, tmp_java_file: Path) -> None:
        extractor = ASTExtractor(Language.JAVA)
        module = extractor.extract_file(tmp_java_file)

        assert module is not None
        export_class = next(c for c in module.classes if c.name == "ExportService")
        assert "EventBus" in export_class.outgoing_components

    def test_extract_nonexistent_file_returns_none(self, tmp_path: Path) -> None:
        extractor = ASTExtractor(Language.JAVA)
        result = extractor.extract_file(tmp_path / "Missing.java")
        assert result is None

    def test_extract_dir(self, tmp_java_file: Path) -> None:
        extractor = ASTExtractor(Language.JAVA)
        modules = extractor.extract_dir(tmp_java_file.parent)
        assert len(modules) == 1
        assert modules[0].module_name == "ExportService"


# ---------------------------------------------------------------------------
# Tests d'extraction AST — Python
# ---------------------------------------------------------------------------


class TestPythonExtractor:
    """Tests de l'extracteur Python via tree-sitter."""

    def test_extract_python_class(self, tmp_python_file: Path) -> None:
        extractor = ASTExtractor(Language.PYTHON)
        module = extractor.extract_file(tmp_python_file)

        assert module is not None
        assert module.language == "python"
        class_names = [c.name for c in module.classes]
        assert "MeterReaderService" in class_names

    def test_extract_python_published_event(self, tmp_python_file: Path) -> None:
        extractor = ASTExtractor(Language.PYTHON)
        module = extractor.extract_file(tmp_python_file)

        assert module is not None
        cls = next(c for c in module.classes if c.name == "MeterReaderService")
        assert "ReadingCompletedEvent" in cls.events_published

    def test_extract_python_subscribed_event(self, tmp_python_file: Path) -> None:
        extractor = ASTExtractor(Language.PYTHON)
        module = extractor.extract_file(tmp_python_file)

        assert module is not None
        cls = next(c for c in module.classes if c.name == "MeterReaderService")
        assert "AlertEvent" in cls.events_subscribed


# ---------------------------------------------------------------------------
# Tests d'extraction AST — C#
# ---------------------------------------------------------------------------


class TestCSharpExtractor:
    """Tests de l'extracteur C# via tree-sitter."""

    def test_extract_csharp_class(self, tmp_csharp_file: Path) -> None:
        extractor = ASTExtractor(Language.CSHARP)
        module = extractor.extract_file(tmp_csharp_file)

        assert module is not None
        assert module.language == "csharp"
        class_names = [c.name for c in module.classes]
        assert "BillingService" in class_names

    def test_extract_csharp_interface(self, tmp_csharp_file: Path) -> None:
        extractor = ASTExtractor(Language.CSHARP)
        module = extractor.extract_file(tmp_csharp_file)

        assert module is not None
        kinds = {c.name: c.kind for c in module.classes}
        assert kinds.get("IBillingHandler") == "interface"

    def test_extract_csharp_declared_event(self, tmp_csharp_file: Path) -> None:
        """Les événements C# déclarés (event keyword) sont détectés."""
        extractor = ASTExtractor(Language.CSHARP)
        module = extractor.extract_file(tmp_csharp_file)

        assert module is not None
        billing = next(c for c in module.classes if c.name == "BillingService")
        # BillingCompleted est déclaré avec le mot-clé event
        assert "BillingCompleted" in billing.events_published

    def test_extract_csharp_namespace(self, tmp_csharp_file: Path) -> None:
        extractor = ASTExtractor(Language.CSHARP)
        module = extractor.extract_file(tmp_csharp_file)

        assert module is not None
        assert module.package is not None
        assert "SmartMetering" in module.package


# ---------------------------------------------------------------------------
# Tests GraphBuilder
# ---------------------------------------------------------------------------


class TestGraphBuilder:
    """Tests de la construction de documents et relations."""

    def test_build_documents_count(self, sample_module: ExtractedModule) -> None:
        builder = GraphBuilder()
        docs = builder.build_documents([sample_module])
        assert len(docs) == 1

    def test_build_document_source_type(self, sample_module: ExtractedModule) -> None:
        builder = GraphBuilder()
        docs = builder.build_documents([sample_module])
        doc = docs[0]
        assert doc.id_source.startswith("code:")
        assert doc.titre.startswith("[Code]")

    def test_build_document_contenu_contient_classes(
        self, sample_module: ExtractedModule
    ) -> None:
        builder = GraphBuilder()
        docs = builder.build_documents([sample_module])
        assert "ExportService" in docs[0].contenu_texte

    def test_build_relations_publie(self, sample_module: ExtractedModule) -> None:
        builder = GraphBuilder()
        relations = builder.build_relations([sample_module])
        publie = [r for r in relations if r.kind == "publie"]
        assert any(r.target == "ExportCompletedEvent" for r in publie)

    def test_build_relations_appelle(self, sample_module: ExtractedModule) -> None:
        builder = GraphBuilder()
        relations = builder.build_relations([sample_module])
        appelle = [r for r in relations if r.kind == "appelle"]
        targets = {r.target for r in appelle}
        assert "EventBus" in targets

    def test_build_relations_source_component(self, sample_module: ExtractedModule) -> None:
        builder = GraphBuilder()
        relations = builder.build_relations([sample_module])
        assert all(r.source_component for r in relations)

    def test_build_relations_confidence(self, sample_module: ExtractedModule) -> None:
        builder = GraphBuilder()
        relations = builder.build_relations([sample_module])
        for rel in relations:
            assert 0.0 <= rel.confidence <= 1.0


# ---------------------------------------------------------------------------
# Tests DocGenerator (LLM mocké)
# ---------------------------------------------------------------------------


class TestDocGenerator:
    """Tests du générateur de documentation (LLM local mocké)."""

    def _mock_llm_response(self) -> dict:
        return {
            "description": "Le module ExportService gère l'export des données de compteurs.",
            "composants": ["ExportService", "IExportHandler"],
            "flux": ["ExportService publie ExportCompletedEvent"],
            "regles_metier": ["L'export déclenche un événement de complétion"],
            "risques": ["Couplage fort avec EventBus"],
        }

    def test_generate_without_llm_returns_partial_doc(
        self, sample_module: ExtractedModule
    ) -> None:
        """Sans LLM disponible, la doc partielle est retournée (pas d'exception)."""
        gen = DocGenerator(base_url="http://localhost:99999", model="test")
        doc = gen.generate(sample_module)

        assert isinstance(doc, ModuleDoc)
        assert doc.module_name == "ExportService"
        assert "ExportService" in doc.classes

    def test_generate_with_mocked_llm(self, sample_module: ExtractedModule) -> None:
        """Avec LLM mocké, la doc est complète."""
        gen = DocGenerator(base_url="http://localhost:11434/v1", model="test")
        llm_data = self._mock_llm_response()

        with patch("httpx.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.json.return_value = {
                "choices": [
                    {"message": {"content": json.dumps(llm_data)}}
                ]
            }
            mock_resp.raise_for_status = MagicMock()
            mock_post.return_value = mock_resp

            doc = gen.generate(sample_module)

        assert doc.description == llm_data["description"]
        assert doc.flux == llm_data["flux"]
        assert doc.regles_metier == llm_data["regles_metier"]

    def test_render_markdown_contains_module_name(
        self, sample_module: ExtractedModule
    ) -> None:
        gen = DocGenerator(base_url="http://localhost:99999", model="test")
        doc = gen.generate(sample_module)
        md = render_markdown(doc)

        assert "ExportService" in md

    def test_render_markdown_obsidian_frontmatter(
        self, sample_module: ExtractedModule
    ) -> None:
        gen = DocGenerator(base_url="http://localhost:99999", model="test")
        doc = gen.generate(sample_module)
        md = render_markdown(doc)

        assert md.startswith("---")
        assert "tags:" in md
        assert "reverse-engineering" in md

    def test_render_markdown_contains_events(
        self, sample_module: ExtractedModule
    ) -> None:
        gen = DocGenerator(base_url="http://localhost:99999", model="test")
        doc = gen.generate(sample_module)
        md = render_markdown(doc)

        assert "ExportCompletedEvent" in md

    def test_generate_dir_creates_files(
        self, sample_module: ExtractedModule, tmp_path: Path
    ) -> None:
        gen = DocGenerator(base_url="http://localhost:99999", model="test")
        generated = gen.generate_dir([sample_module], out_dir=tmp_path)

        assert len(generated) == 1
        assert generated[0].exists()
        assert generated[0].suffix == ".md"

    def test_generate_dir_with_module_filter(
        self, sample_module: ExtractedModule, tmp_path: Path
    ) -> None:
        gen = DocGenerator(base_url="http://localhost:99999", model="test")
        # Filtre qui correspond
        generated_match = gen.generate_dir(
            [sample_module], out_dir=tmp_path, module_filter="ExportService"
        )
        assert len(generated_match) == 1

        # Filtre qui ne correspond pas
        generated_no_match = gen.generate_dir(
            [sample_module],
            out_dir=tmp_path / "sub",
            module_filter="UnknownModule",
        )
        assert len(generated_no_match) == 0
