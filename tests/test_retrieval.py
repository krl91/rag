"""
Tests du module retrieval (Phase 3).

Tests unitaires (sans réseau, sans modèle réel) :
- search : détection de date depuis la question, construction des filtres
- reranker : reranking sur cas synthétiques (CrossEncoder mocké)
- context : assemblage du contexte, respect du budget de tokens,
            regroupement par type, format des sources
"""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from kb_smart_metering.retrieval.context import (
    ContextItem,
    ContextSource,
    ContextType,
    assemble_context,
    estimate_tokens,
)
from kb_smart_metering.retrieval.reranker import RankedCandidate, rerank
from kb_smart_metering.retrieval.search import (
    VERSION_DATE_MAP,
    SearchCandidate,
    detect_date_from_question,
)


# ---------------------------------------------------------------------------
# search.py — détection de date depuis la question
# ---------------------------------------------------------------------------


class TestDetectDateFromQuestion:
    """Tests de la détection de date/version dans la question."""

    def test_detecte_pr2(self) -> None:
        date = detect_date_from_question("Quelle est l'architecture en PR2 ?")
        assert date == VERSION_DATE_MAP["pr2"]

    def test_detecte_pr_avec_espace(self) -> None:
        date = detect_date_from_question("Les décisions prises en PR 3.")
        assert date == VERSION_DATE_MAP["pr3"]

    def test_detecte_sprint1(self) -> None:
        date = detect_date_from_question("Qui était responsable sprint1 ?")
        assert date == VERSION_DATE_MAP["sprint1"]

    def test_detecte_sprint_avec_espace(self) -> None:
        date = detect_date_from_question("Actions du sprint 2")
        assert date == VERSION_DATE_MAP["sprint2"]

    def test_insensible_a_la_casse(self) -> None:
        date = detect_date_from_question("Décisions en PR2")
        assert date == detect_date_from_question("décisions en pr2")

    def test_pas_de_version_retourne_none(self) -> None:
        assert detect_date_from_question("Quelle est l'architecture actuelle ?") is None
        assert detect_date_from_question("") is None

    def test_version_inconnue_retourne_none(self) -> None:
        # PR99 n'existe pas dans VERSION_DATE_MAP
        assert detect_date_from_question("Situation en PR99") is None


# ---------------------------------------------------------------------------
# reranker.py — reranking sur cas synthétiques (CrossEncoder mocké)
# ---------------------------------------------------------------------------


def _make_mock_cross_encoder(scores: list[float]):
    """Crée un mock CrossEncoder dont predict() retourne scores."""
    mock = MagicMock()
    mock.predict.return_value = scores
    return mock


class TestRerank:
    """Tests du reranker avec CrossEncoder mocké."""

    def test_trie_par_score_decroissant(self) -> None:
        candidates = ["texte A", "texte B", "texte C"]
        scores = [0.3, 0.9, 0.1]

        with patch("kb_smart_metering.retrieval.reranker._reranker_instance", _make_mock_cross_encoder(scores)):
            result = rerank("question test", candidates)

        assert len(result) == 3
        assert result[0].text == "texte B"  # score 0.9
        assert result[1].text == "texte A"  # score 0.3
        assert result[2].text == "texte C"  # score 0.1
        assert result[0].score > result[1].score > result[2].score

    def test_original_index_correct(self) -> None:
        candidates = ["A", "B", "C"]
        scores = [0.5, 0.8, 0.2]

        with patch("kb_smart_metering.retrieval.reranker._reranker_instance", _make_mock_cross_encoder(scores)):
            result = rerank("question", candidates)

        # B (index 1) doit être premier
        assert result[0].original_index == 1
        assert result[1].original_index == 0
        assert result[2].original_index == 2

    def test_limite_top_n(self) -> None:
        candidates = ["A", "B", "C", "D", "E"]
        scores = [0.1, 0.5, 0.9, 0.3, 0.7]

        with patch("kb_smart_metering.retrieval.reranker._reranker_instance", _make_mock_cross_encoder(scores)):
            result = rerank("question", candidates, top_n=3)

        assert len(result) == 3
        assert result[0].score == 0.9  # C
        assert result[1].score == 0.7  # E
        assert result[2].score == 0.5  # B

    def test_liste_vide_retourne_liste_vide(self) -> None:
        with patch("kb_smart_metering.retrieval.reranker._reranker_instance", MagicMock()):
            result = rerank("question", [])
        assert result == []

    def test_metadata_propagee(self) -> None:
        candidates = ["A", "B"]
        scores = [0.4, 0.9]
        meta = [{"source": "jira-1"}, {"source": "conf-2"}]

        with patch("kb_smart_metering.retrieval.reranker._reranker_instance", _make_mock_cross_encoder(scores)):
            result = rerank("question", candidates, metadata=meta)

        # B (score 0.9) en premier avec sa metadata
        assert result[0].metadata == {"source": "conf-2"}
        assert result[1].metadata == {"source": "jira-1"}

    def test_metadata_longueur_incorrecte_leve_erreur(self) -> None:
        candidates = ["A", "B", "C"]
        scores = [0.1, 0.2, 0.3]
        meta = [{"x": 1}]  # longueur incorrecte

        with patch("kb_smart_metering.retrieval.reranker._reranker_instance", _make_mock_cross_encoder(scores)):
            with pytest.raises(ValueError, match="même longueur"):
                rerank("question", candidates, metadata=meta)

    def test_cross_encoder_appele_avec_paires(self) -> None:
        """Vérifie que CrossEncoder reçoit bien des paires (question, candidat)."""
        candidates = ["fait 1", "fait 2"]
        mock_encoder = _make_mock_cross_encoder([0.5, 0.8])

        with patch("kb_smart_metering.retrieval.reranker._reranker_instance", mock_encoder):
            rerank("ma question", candidates)

        mock_encoder.predict.assert_called_once_with(
            [("ma question", "fait 1"), ("ma question", "fait 2")]
        )


# ---------------------------------------------------------------------------
# reranker.py — chargement lazy du singleton
# ---------------------------------------------------------------------------


class TestRerankerLazySingleton:
    """Vérifie que le modèle n'est chargé qu'une seule fois."""

    def test_singleton_reutilise_sans_recreer_crossencoder(self) -> None:
        """
        Quand _reranker_instance est déjà chargé, _get_reranker() le retourne
        sans instancier un nouveau CrossEncoder.
        """
        import kb_smart_metering.retrieval.reranker as reranker_module

        original = reranker_module._reranker_instance
        try:
            mock_encoder = _make_mock_cross_encoder([0.5, 0.3])
            # Injecter le mock comme singleton déjà chargé
            reranker_module._reranker_instance = mock_encoder

            with patch("sentence_transformers.CrossEncoder") as mock_cls:
                result = reranker_module._get_reranker()
                # CrossEncoder ne doit pas être réinstancié
                mock_cls.assert_not_called()

            assert result is mock_encoder
        finally:
            reranker_module._reranker_instance = original

    def test_singleton_reutilise_par_rerank(self) -> None:
        """
        Deux appels successifs à rerank() utilisent le même instance CrossEncoder.
        """
        import kb_smart_metering.retrieval.reranker as reranker_module

        original = reranker_module._reranker_instance
        try:
            mock_encoder = _make_mock_cross_encoder([0.9, 0.1])
            reranker_module._reranker_instance = mock_encoder

            rerank("q1", ["A", "B"])
            rerank("q2", ["A", "B"])

            # predict appelé une fois par appel rerank()
            assert mock_encoder.predict.call_count == 2
        finally:
            reranker_module._reranker_instance = original


# ---------------------------------------------------------------------------
# context.py — assemblage du contexte
# ---------------------------------------------------------------------------


def _make_item(
    content: str,
    ctx_type: ContextType = ContextType.FACT,
    source_id: str = "https://example.com",
    source_type: str = "confluence",
    valid_at: str | None = None,
    page: int | None = None,
) -> ContextItem:
    return ContextItem(
        type=ctx_type,
        content=content,
        source=ContextSource(type=source_type, identifier=source_id, page=page),
        valid_at=valid_at,
    )


class TestEstimateTokens:
    """Tests de l'estimation de tokens."""

    def test_texte_vide(self) -> None:
        assert estimate_tokens("") >= 1

    def test_texte_court(self) -> None:
        # "hello world" → 2 mots → ~3 tokens
        result = estimate_tokens("hello world")
        assert result > 0
        assert isinstance(result, int)

    def test_plus_de_mots_plus_de_tokens(self) -> None:
        court = estimate_tokens("mot")
        long_ = estimate_tokens("mot " * 100)
        assert long_ > court


class TestAssembleContext:
    """Tests de l'assemblage du contexte pour le LLM."""

    def test_context_contient_la_question(self) -> None:
        ctx = assemble_context([], "Ma question de test ?")
        assert "Ma question de test ?" in ctx

    def test_context_contient_header_question(self) -> None:
        ctx = assemble_context([], "question")
        assert "## Question" in ctx

    def test_item_fact_inclus(self) -> None:
        item = _make_item("Le système MDM v3 est en production.", ContextType.FACT)
        ctx = assemble_context([item], "question")
        assert "Le système MDM v3 est en production." in ctx
        assert "## Faits" in ctx

    def test_source_incluse_dans_contexte(self) -> None:
        item = _make_item(
            "Décision d'adopter Kafka.",
            ContextType.DECISION,
            source_id="https://jira.example.com/PROJ-42",
            source_type="jira",
        )
        ctx = assemble_context([item], "question")
        assert "https://jira.example.com/PROJ-42" in ctx
        assert "## Décisions" in ctx

    def test_source_avec_page_incluse(self) -> None:
        item = _make_item(
            "Fait extrait du rapport.",
            source_id="/docs/rapport.pdf",
            page=12,
        )
        ctx = assemble_context([item], "question")
        assert "p.12" in ctx

    def test_valid_at_incluse(self) -> None:
        item = _make_item(
            "Fait daté.",
            valid_at="2023-12-01",
        )
        ctx = assemble_context([item], "question")
        assert "2023-12-01" in ctx

    def test_regroupement_par_type(self) -> None:
        items = [
            _make_item("Fait 1", ContextType.FACT),
            _make_item("Décision 1", ContextType.DECISION),
            _make_item("Action 1", ContextType.ACTION),
        ]
        ctx = assemble_context(items, "question")
        assert "## Faits" in ctx
        assert "## Décisions" in ctx
        assert "## Actions" in ctx

    def test_ordre_des_sections(self) -> None:
        items = [
            _make_item("Réunion 1", ContextType.MEETING),
            _make_item("Décision 1", ContextType.DECISION),
            _make_item("Fait 1", ContextType.FACT),
        ]
        ctx = assemble_context(items, "question")
        pos_faits = ctx.index("## Faits")
        pos_decisions = ctx.index("## Décisions")
        pos_reunions = ctx.index("## Réunions")
        # Faits avant Décisions avant Réunions
        assert pos_faits < pos_decisions < pos_reunions

    def test_budget_tokens_respecte(self) -> None:
        """Aucun contexte assemblé ne doit dépasser (avec marge) le budget."""
        # 100 items de contenu long
        items = [
            _make_item(
                "Fait très détaillé avec beaucoup de mots pour tester le budget " * 5,
                ContextType.FACT,
                source_id=f"https://exemple.com/doc-{i}",
            )
            for i in range(100)
        ]
        budget = 300
        ctx = assemble_context(items, "question courte", token_budget=budget)
        estimated = estimate_tokens(ctx)
        # Tolérance de 20 % au-delà du budget (dû à la granularité des entrées)
        assert estimated <= budget * 1.2, (
            f"Contexte trop long : {estimated} tokens estimés (budget={budget})"
        )

    def test_budget_tres_petit_retourne_quand_meme_la_question(self) -> None:
        items = [_make_item("Contenu très long " * 50)]
        ctx = assemble_context(items, "question", token_budget=5)
        # La question doit toujours être présente
        assert "## Question" in ctx

    def test_liste_vide_retourne_contexte_minimaliste(self) -> None:
        ctx = assemble_context([], "ma question")
        assert "ma question" in ctx
        # Aucune section de contenu
        assert "## Faits" not in ctx
        assert "## Décisions" not in ctx

    def test_items_de_types_multiples_sans_doublon(self) -> None:
        items = [
            _make_item("Fait A", ContextType.FACT),
            _make_item("Fait B", ContextType.FACT),
            _make_item("Action X", ContextType.ACTION),
        ]
        ctx = assemble_context(items, "q")
        # Une seule section Faits
        assert ctx.count("## Faits") == 1
        # Deux faits présents
        assert "Fait A" in ctx
        assert "Fait B" in ctx

    def test_contexte_sans_section_vide(self) -> None:
        """Les types sans items ne doivent pas générer de section vide."""
        item = _make_item("Fait unique", ContextType.FACT)
        ctx = assemble_context([item], "question")
        assert "## Actions" not in ctx
        assert "## Réunions" not in ctx
        assert "## Risques" not in ctx
