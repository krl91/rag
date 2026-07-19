"""
Tests du module assistant (Phase 4).

Tests unitaires sans appel réseau réel — LLM et Graphiti mockés.
Vérifient :
  - llm.py   : parsing JSON, retry sur JSON invalide, validation Pydantic
  - render.py : format markdown Obsidian, liens cliquables, sections vides
  - chain.py  : orchestration (retrieval + reranker + LLM mockés)
  - API       : POST /ask, GET /health (via TestClient FastAPI)
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from kb_smart_metering.assistant.llm import (
    LLMAssistant,
    ReponseStructuree,
    _build_user_message,
    _extract_json,
)
from kb_smart_metering.assistant.render import _as_link, _bullet_list, to_markdown

# ---------------------------------------------------------------------------
# Fixture — réponse structurée type pour les tests
# ---------------------------------------------------------------------------

CANNED_RESPONSE = ReponseStructuree(
    resume="Le compteur Linky est déployé par Enedis.",
    facts=["Linky est un compteur communicant.", "Plus de 35 millions de compteurs déployés."],
    decisions=["Adoption du protocole PLC G3 pour les communications."],
    actions=["Vérifier la compatibilité des concentrateurs."],
    risks=["Risque de saturation réseau lors des relevés simultanés."],
    sources=["https://jira.example.com/SMART-42", "Confluence : page Architecture Linky"],
)

CANNED_JSON = json.dumps(CANNED_RESPONSE.model_dump(), ensure_ascii=False)


# ===========================================================================
# llm.py — _extract_json
# ===========================================================================


class TestExtractJson:
    """Tests de l'extraction JSON depuis la réponse brute du LLM."""

    def test_json_brut(self) -> None:
        data = _extract_json('{"resume": "ok", "facts": []}')
        assert data["resume"] == "ok"

    def test_bloc_fenced_json(self) -> None:
        text = '```json\n{"resume": "ok", "facts": []}\n```'
        data = _extract_json(text)
        assert data["resume"] == "ok"

    def test_bloc_fenced_sans_langue(self) -> None:
        text = '```\n{"resume": "ok", "facts": []}\n```'
        data = _extract_json(text)
        assert data["resume"] == "ok"

    def test_json_invalide_leve_erreur(self) -> None:
        with pytest.raises(json.JSONDecodeError):
            _extract_json("pas du json du tout")


# ===========================================================================
# llm.py — _build_user_message
# ===========================================================================


class TestBuildUserMessage:
    """Tests de la construction du message utilisateur."""

    def test_contient_question(self) -> None:
        msg = _build_user_message("Quelle est l'architecture ?", "contexte ici")
        assert "Quelle est l'architecture ?" in msg

    def test_contient_contexte(self) -> None:
        msg = _build_user_message("question", "contexte important")
        assert "contexte important" in msg

    def test_contient_schema(self) -> None:
        msg = _build_user_message("q", "c")
        assert "resume" in msg
        assert "facts" in msg


# ===========================================================================
# llm.py — LLMAssistant.ask (LLM HTTP mocké)
# ===========================================================================


def _make_http_response(payload: dict) -> MagicMock:
    """Crée un mock httpx.Response retournant le payload donné."""
    mock_resp = MagicMock()
    mock_resp.raise_for_status.return_value = None
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": json.dumps(payload, ensure_ascii=False)}}]
    }
    return mock_resp


class TestLLMAssistant:
    """Tests du client LLM avec HTTP mocké."""

    def test_ask_retourne_reponse_structuree(self) -> None:
        assistant = LLMAssistant(base_url="http://localhost:11434/v1", model="mistral:7b")
        with patch("kb_smart_metering.assistant.llm.httpx.post") as mock_post:
            mock_post.return_value = _make_http_response(CANNED_RESPONSE.model_dump())
            result = assistant.ask("Quelle est l'architecture ?", "contexte ici")

        assert isinstance(result, ReponseStructuree)
        assert result.resume == CANNED_RESPONSE.resume
        assert result.facts == CANNED_RESPONSE.facts
        assert result.decisions == CANNED_RESPONSE.decisions

    def test_ask_retry_sur_json_invalide(self) -> None:
        """Le premier appel retourne du JSON invalide, le second retourne un JSON valide."""
        assistant = LLMAssistant(base_url="http://localhost:11434/v1", model="mistral:7b")

        invalid_resp = MagicMock()
        invalid_resp.raise_for_status.return_value = None
        invalid_resp.json.return_value = {
            "choices": [{"message": {"content": "ce n'est pas du JSON"}}]
        }

        valid_resp = _make_http_response(CANNED_RESPONSE.model_dump())

        with patch("kb_smart_metering.assistant.llm.httpx.post") as mock_post:
            mock_post.side_effect = [invalid_resp, valid_resp]
            result = assistant.ask("question", "contexte")

        assert mock_post.call_count == 2
        assert isinstance(result, ReponseStructuree)

    def test_ask_leve_erreur_apres_deux_echecs(self) -> None:
        """Deux tentatives échouées lèvent ValueError."""
        assistant = LLMAssistant(base_url="http://localhost:11434/v1", model="mistral:7b")

        bad_resp = MagicMock()
        bad_resp.raise_for_status.return_value = None
        bad_resp.json.return_value = {
            "choices": [{"message": {"content": "not json"}}]
        }

        with patch("kb_smart_metering.assistant.llm.httpx.post") as mock_post:
            mock_post.return_value = bad_resp
            with pytest.raises(ValueError, match="non parseable"):
                assistant.ask("question", "contexte")

        assert mock_post.call_count == 2

    def test_ask_valide_schema_pydantic(self) -> None:
        """Une réponse avec un champ requis manquant (resume absent) → retry puis erreur."""
        assistant = LLMAssistant(base_url="http://localhost:11434/v1", model="mistral:7b")

        missing_resume = {"facts": ["un fait"], "decisions": [], "actions": [], "risks": [], "sources": []}
        bad_resp = MagicMock()
        bad_resp.raise_for_status.return_value = None
        bad_resp.json.return_value = {
            "choices": [{"message": {"content": json.dumps(missing_resume)}}]
        }

        with patch("kb_smart_metering.assistant.llm.httpx.post") as mock_post:
            mock_post.return_value = bad_resp
            with pytest.raises(ValueError):
                assistant.ask("question", "contexte")


# ===========================================================================
# render.py — to_markdown, _as_link, _bullet_list
# ===========================================================================


class TestAsLink:
    """Tests de la transformation source → lien markdown."""

    def test_url_simple(self) -> None:
        link = _as_link("https://jira.example.com/SMART-42")
        assert "https://jira.example.com/SMART-42" in link
        assert link.startswith("<") or "[" in link

    def test_url_avec_label(self) -> None:
        link = _as_link("Ticket SMART-42 : https://jira.example.com/SMART-42")
        assert "Ticket SMART-42" in link
        assert "https://jira.example.com/SMART-42" in link

    def test_sans_url(self) -> None:
        source = "Confluence : page Architecture"
        assert _as_link(source) == source


class TestBulletList:
    """Tests du formatage liste à puces."""

    def test_items_non_vides(self) -> None:
        result = _bullet_list(["item 1", "item 2"])
        assert "- item 1" in result
        assert "- item 2" in result

    def test_liste_vide(self) -> None:
        assert "Aucun" in _bullet_list([])


class TestToMarkdown:
    """Tests du rendu Markdown Obsidian."""

    def test_titre_h1_est_la_question(self) -> None:
        md = to_markdown("Mon titre ?", CANNED_RESPONSE)
        assert md.startswith("# Mon titre ?")

    def test_section_resume_presente(self) -> None:
        md = to_markdown("question", CANNED_RESPONSE)
        assert "## Résumé" in md
        assert CANNED_RESPONSE.resume in md

    def test_section_decisions_presente(self) -> None:
        md = to_markdown("question", CANNED_RESPONSE)
        assert "## Décisions" in md
        assert CANNED_RESPONSE.decisions[0] in md

    def test_section_actions_presente(self) -> None:
        md = to_markdown("question", CANNED_RESPONSE)
        assert "## Actions" in md

    def test_section_risques_presente(self) -> None:
        md = to_markdown("question", CANNED_RESPONSE)
        assert "## Risques" in md

    def test_section_sources_presente(self) -> None:
        md = to_markdown("question", CANNED_RESPONSE)
        assert "## Sources" in md

    def test_url_dans_sources_est_cliquable(self) -> None:
        md = to_markdown("question", CANNED_RESPONSE)
        # La source jira.example.com doit apparaître comme lien
        assert "jira.example.com" in md
        assert "](" in md or "<http" in md

    def test_sections_vides_absentes(self) -> None:
        """facts et decisions vides → sections omises."""
        reponse_minimale = ReponseStructuree(
            resume="résumé",
            facts=[],
            decisions=[],
            actions=[],
            risks=[],
            sources=[],
        )
        md = to_markdown("question", reponse_minimale)
        assert "## Faits" not in md
        assert "## Décisions" not in md
        assert "## Sources" in md  # toujours affichée

    def test_sources_vides_affichent_aucune(self) -> None:
        reponse = ReponseStructuree(resume="r", sources=[])
        md = to_markdown("q", reponse)
        assert "Aucune source" in md


# ===========================================================================
# API FastAPI — GET /health, POST /ask
# ===========================================================================


@pytest.fixture()
def api_client():
    """Client de test FastAPI sans appel réseau."""
    from kb_smart_metering.api.app import app

    return TestClient(app)


class TestHealthEndpoint:
    """Tests du endpoint GET /health."""

    def test_health_retourne_200(self, api_client: TestClient) -> None:
        response = api_client.get("/health")
        assert response.status_code == 200

    def test_health_retourne_status_ok(self, api_client: TestClient) -> None:
        data = api_client.get("/health").json()
        assert data["status"] == "ok"


class TestAskEndpoint:
    """Tests du endpoint POST /ask avec AssistantChain mockée."""

    def _mock_chain_run(self) -> MagicMock:
        """Crée un mock de AssistantChain.run retournant CANNED_RESPONSE."""
        mock_chain = MagicMock()
        mock_chain.run = AsyncMock(return_value=CANNED_RESPONSE)
        mock_chain.render_markdown.return_value = to_markdown("question test", CANNED_RESPONSE)
        return mock_chain

    def test_ask_retourne_200(self, api_client: TestClient) -> None:
        with patch("kb_smart_metering.api.routes.AssistantChain") as MockChain:
            MockChain.return_value = self._mock_chain_run()
            response = api_client.post("/ask", json={"question": "question test"})
        assert response.status_code == 200

    def test_ask_schema_reponse(self, api_client: TestClient) -> None:
        with patch("kb_smart_metering.api.routes.AssistantChain") as MockChain:
            MockChain.return_value = self._mock_chain_run()
            data = api_client.post("/ask", json={"question": "question test"}).json()

        assert "question" in data
        assert "reponse" in data
        assert "markdown" in data
        reponse = data["reponse"]
        assert "resume" in reponse
        assert "facts" in reponse
        assert "decisions" in reponse
        assert "actions" in reponse
        assert "risks" in reponse
        assert "sources" in reponse

    def test_ask_avec_as_of_date(self, api_client: TestClient) -> None:
        with patch("kb_smart_metering.api.routes.AssistantChain") as MockChain:
            mock = self._mock_chain_run()
            MockChain.return_value = mock
            api_client.post(
                "/ask",
                json={"question": "question", "as_of_date": "2023-12-01T00:00:00"},
            )
        mock.run.assert_called_once()
        _, kwargs = mock.run.call_args
        assert kwargs.get("as_of_date") is not None

    def test_ask_avec_entity_types(self, api_client: TestClient) -> None:
        with patch("kb_smart_metering.api.routes.AssistantChain") as MockChain:
            mock = self._mock_chain_run()
            MockChain.return_value = mock
            api_client.post(
                "/ask",
                json={"question": "question", "entity_types": ["Decision", "Action"]},
            )
        mock.run.assert_called_once()
        _, kwargs = mock.run.call_args
        assert kwargs.get("entity_types") == ["Decision", "Action"]

    def test_ask_erreur_interne_retourne_500(self, api_client: TestClient) -> None:
        with patch("kb_smart_metering.api.routes.AssistantChain") as MockChain:
            mock = MagicMock()
            mock.run = AsyncMock(side_effect=RuntimeError("Neo4j inaccessible"))
            MockChain.return_value = mock
            response = api_client.post("/ask", json={"question": "question"})
        assert response.status_code == 500

    def test_ask_markdown_contient_titre(self, api_client: TestClient) -> None:
        with patch("kb_smart_metering.api.routes.AssistantChain") as MockChain:
            MockChain.return_value = self._mock_chain_run()
            data = api_client.post("/ask", json={"question": "question test"}).json()
        assert "# question test" in data["markdown"]


class TestSearchEndpoint:
    """Tests du endpoint POST /search — retrieval seul, aucun appel LLM."""

    def _mock_chain_build_context(self, contexte: str = "contexte assemblé") -> MagicMock:
        mock_chain = MagicMock()
        mock_chain.build_context = AsyncMock(return_value=contexte)
        return mock_chain

    def test_search_retourne_200(self, api_client: TestClient) -> None:
        with patch("kb_smart_metering.api.routes.AssistantChain") as MockChain:
            MockChain.return_value = self._mock_chain_build_context()
            response = api_client.post("/search", json={"question": "question test"})
        assert response.status_code == 200

    def test_search_ne_construit_pas_de_reponse_llm(self, api_client: TestClient) -> None:
        with patch("kb_smart_metering.api.routes.AssistantChain") as MockChain:
            MockChain.return_value = self._mock_chain_build_context()
            data = api_client.post("/search", json={"question": "question test"}).json()
        assert "reponse" not in data
        assert "markdown" not in data
        assert "contexte" in data

    def test_search_appelle_build_context_pas_run(self, api_client: TestClient) -> None:
        with patch("kb_smart_metering.api.routes.AssistantChain") as MockChain:
            mock = self._mock_chain_build_context()
            MockChain.return_value = mock
            api_client.post("/search", json={"question": "question test"})
        mock.build_context.assert_awaited_once()
        mock.run.assert_not_called()

    def test_search_avec_as_of_date_et_entity_types(self, api_client: TestClient) -> None:
        with patch("kb_smart_metering.api.routes.AssistantChain") as MockChain:
            mock = self._mock_chain_build_context()
            MockChain.return_value = mock
            api_client.post(
                "/search",
                json={
                    "question": "question",
                    "as_of_date": "2023-12-01T00:00:00",
                    "entity_types": ["Decision"],
                },
            )
        _, kwargs = mock.build_context.call_args
        assert kwargs.get("as_of_date") is not None
        assert kwargs.get("entity_types") == ["Decision"]

    def test_search_erreur_interne_retourne_500(self, api_client: TestClient) -> None:
        with patch("kb_smart_metering.api.routes.AssistantChain") as MockChain:
            mock = MagicMock()
            mock.build_context = AsyncMock(side_effect=RuntimeError("Neo4j inaccessible"))
            MockChain.return_value = mock
            response = api_client.post("/search", json={"question": "question"})
        assert response.status_code == 500
