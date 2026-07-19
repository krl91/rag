# Portage Windows — Problème 3 : `asyncio.get_event_loop()` et ProactorEventLoop

## Contexte du projet

`kb-smart-metering` utilise asyncio de façon intensive : ingestion Graphiti,
embeddings BGE-M3 (sentence-transformers), driver Neo4j async, et serveur
FastAPI via uvicorn. Le fichier concerné est
`src/kb_smart_metering/ingestion/embedder.py`.

---

## Principe directeur

**Privilégier systématiquement ce qui est déjà disponible** dans la
bibliothèque standard Python avant d'introduire des dépendances externes :
- `asyncio.get_running_loop()` est disponible depuis Python 3.7 et est la
  correction directe — l'utiliser sans bibliothèque tierce.
- La configuration de la boucle d'événements (`asyncio.set_event_loop_policy`)
  est dans la stdlib — pas besoin d'outil supplémentaire.
- Ne recommander une dépendance externe que si la stdlib est insuffisante.

---

## Description du problème

### Problème 1 — `asyncio.get_event_loop()` déprécié

Dans `src/kb_smart_metering/ingestion/embedder.py`, ligne 69 :

```python
async def create(self, input_data: ...) -> list[float]:
    ...
    loop = asyncio.get_event_loop()          # ← DÉPRÉCIÉ depuis Python 3.10
    encode_fn = partial(self._encode_sync, text)
    return await loop.run_in_executor(None, encode_fn)
```

`asyncio.get_event_loop()` est déprécié depuis Python 3.10 et émet un
`DeprecationWarning`. En Python 3.12+, il lève une `DeprecationWarning`
qui peut devenir une erreur selon la configuration de warnings.

La version correcte est `asyncio.get_running_loop()` qui retourne la boucle
**en cours d'exécution** depuis un contexte `async`, sans effet de bord.

### Problème 2 — ProactorEventLoop sous Windows

Sur Windows, Python 3.8+ utilise `ProactorEventLoop` par défaut (au lieu de
`SelectorEventLoop` sur Linux/macOS). Cette différence peut impacter :

- Le driver `neo4j` async (qui utilise des sockets).
- Les bibliothèques qui font des appels `subprocess` ou des I/O fichiers en
  mode async.
- `uvicorn` avec FastAPI (qui peut chercher à configurer sa propre boucle).

Les symptômes possibles : `RuntimeError: Event loop is closed`, erreurs SSL,
ou comportements non déterministes dans les tests async sous Windows.

### Classe complète concernée

```python
class BGEM3Embedder(EmbedderClient):

    def __init__(self, model_name: str = "BAAI/bge-m3") -> None:
        self._model_name = model_name
        self._model: SentenceTransformer | None = None

    def _get_model(self) -> SentenceTransformer:
        if self._model is None:
            logger.info("Chargement du modèle d'embedding : %s", self._model_name)
            self._model = SentenceTransformer(self._model_name)
        return self._model

    def _encode_sync(self, text: str) -> list[float]:
        model = self._get_model()
        embedding = model.encode(text, normalize_embeddings=True)
        if hasattr(embedding, "tolist"):
            return embedding.tolist()
        return list(embedding)

    async def create(
        self,
        input_data: str | list[str] | Iterable[int] | Iterable[Iterable[int]],
    ) -> list[float]:
        if isinstance(input_data, str):
            text = input_data
        elif isinstance(input_data, list) and input_data:
            first = input_data[0]
            text = first if isinstance(first, str) else str(first)
        else:
            text = str(input_data)

        loop = asyncio.get_event_loop()          # ← À CORRIGER
        encode_fn = partial(self._encode_sync, text)
        return await loop.run_in_executor(None, encode_fn)
```

---

## Ce que tu dois analyser

### Correction de `get_event_loop()`

1. Remplacer `asyncio.get_event_loop()` par `asyncio.get_running_loop()`.
   Vérifier que la méthode `create()` est toujours décorée `async` (elle l'est),
   ce qui garantit qu'une boucle est en cours d'exécution lors de l'appel.
2. Confirmer que ce changement est rétrocompatible Python 3.11+.
3. Vérifier les tests existants dans `tests/test_ingestion.py` : utilisent-ils
   des mocks pour `BGEM3Embedder` ? Le changement les impacte-t-il ?

### Compatibilité ProactorEventLoop (Windows)

1. Le driver `neo4j` Python (package `neo4j>=5.20.0`) est-il compatible
   `ProactorEventLoop` ? Vérifier les issues connues dans son tracker GitHub.
2. `uvicorn` gère-t-il correctement `ProactorEventLoop` sur Windows ? Depuis
   quelle version ?
3. Si des incompatibilités existent, est-il nécessaire de forcer
   `SelectorEventLoop` en entrée de programme ? Si oui, où placer cette
   configuration (dans `cli.py` ? dans `api/app.py` ?) :

```python
import asyncio
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
```

4. Quels sont les risques et contre-indications de forcer `SelectorEventLoop`
   sur Windows ?

### Tests pytest-asyncio sous Windows

1. `pytest-asyncio` en mode `asyncio_mode = "auto"` (configuré dans
   `pyproject.toml`) est-il compatible avec `ProactorEventLoop` ?
2. Y a-t-il des configurations spécifiques à ajouter dans `pyproject.toml`
   ou `conftest.py` pour que les tests async passent sur Windows ?

---

## Contraintes du projet

- Python 3.11+.
- `pytest-asyncio>=0.23.0` avec `asyncio_mode = "auto"`.
- Ne pas changer l'interface publique de `BGEM3Embedder` (elle implémente
  `EmbedderClient` de `graphiti-core`).
- Les modifications doivent rester transparentes pour macOS/Linux.

---

## Livrable attendu

- Le diff exact à appliquer dans `src/kb_smart_metering/ingestion/embedder.py`.
- Si nécessaire, le code de configuration de la boucle d'événements à placer
  dans `src/kb_smart_metering/cli.py` et/ou `src/kb_smart_metering/api/app.py`.
- Un résumé des tests à exécuter pour valider la correction sous Windows.
