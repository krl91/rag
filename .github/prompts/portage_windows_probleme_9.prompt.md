# Portage Windows — Problème 9 : `sentence-transformers` et installation de PyTorch sous Windows

## Contexte du projet

`kb-smart-metering` utilise des embeddings locaux BGE-M3 et un reranker
BGE-reranker-v2-m3 via `sentence-transformers`. Ces modèles sont utilisés
dans le pipeline d'ingestion (`embedder.py`) et le retrieval (`reranker.py`).

```toml
"sentence-transformers>=3.0.0",
```

---

## Principe directeur

**Privilégier systématiquement ce qui est déjà disponible** sur la machine :
- Si PyTorch est déjà installé (quelle que soit la variante CPU/CUDA),
  l'utiliser directement sans forcer une réinstallation.
- Si un GPU NVIDIA est présent et CUDA disponible, ne pas dégrader vers la
  variante CPU.
- N'intervenir sur la configuration `uv` / PyTorch que si l'installation
  échoue réellement ou si la variante installée est inadaptée.
- La variable `HF_HOME` ne doit être imposée que si le chemin par défaut
  pose un problème concret (espaces, longueur, permissions).

---

## Description du problème

`sentence-transformers` dépend de **PyTorch** comme dépendance transitive.
PyTorch est une bibliothèque volumineuse (~1–2 Go selon la variante) dont
l'installation sur Windows présente des complexités spécifiques :

### Variants PyTorch

PyTorch publie plusieurs variantes selon le matériel :
- `torch` CPU only (~200 Mo)
- `torch` + CUDA 11.8 (~2 Go)
- `torch` + CUDA 12.1 (~2 Go)
- `torch` + ROCm (AMD, Linux uniquement)

Sur PyPI standard, `pip install torch` installe la variante CUDA qui est
**très volumineuse** même si aucun GPU n'est présent. La variante CPU
nécessite d'utiliser l'index PyTorch officiel :

```
pip install torch --index-url https://download.pytorch.org/whl/cpu
```

### Problème avec `uv sync`

`uv sync --all-extras` utilise PyPI par défaut. Sans configuration explicite,
il installera la variante CUDA de PyTorch sur Windows, ce qui :
1. Consomme 2 Go de disque inutilement (si pas de GPU NVIDIA).
2. Peut échouer ou être très lent sur certaines connexions.
3. Peut installer une version incompatible avec les drivers CUDA disponibles.

### Modèles volumeux

`BAAI/bge-m3` (embeddings) et `BAAI/bge-reranker-v2-m3` (reranker) sont
téléchargés depuis HuggingFace Hub au premier lancement :
- `bge-m3` : ~2.3 Go
- `bge-reranker-v2-m3` : ~2.3 Go

Le répertoire de cache HuggingFace est par défaut :
- Linux : `~/.cache/huggingface/`
- macOS : `~/.cache/huggingface/`
- **Windows : `C:\Users\<user>\.cache\huggingface\`** (chemin avec espaces possibles)

Des espaces dans le chemin de cache peuvent causer des problèmes avec certaines
bibliothèques qui construisent des commandes shell.

---

## Ce que tu dois analyser

### 1. Configuration de `uv` pour PyTorch CPU sous Windows

`uv` supporte la configuration d'index alternatifs via `pyproject.toml` ou
`uv.toml`. Proposer une configuration qui :

- Installe la variante CPU de PyTorch par défaut sur toutes les plateformes.
- Ou installe CPU sur Windows et laisse l'utilisateur choisir GPU sur Linux.

Documentation de référence :
- <https://docs.astral.sh/uv/guides/integration/pytorch/>

Exemple de configuration à évaluer :

```toml
[tool.uv.sources]
torch = [
    { index = "pytorch-cpu", marker = "sys_platform == 'win32'" },
]

[[tool.uv.index]]
name = "pytorch-cpu"
url = "https://download.pytorch.org/whl/cpu"
explicit = true
```

### 2. Variables d'environnement pour le cache HuggingFace

Vérifier si la variable `HF_HOME` permet de rediriger le cache vers un chemin
sans espaces sur Windows :

```env
HF_HOME=C:\kb-cache\huggingface
```

- Ajouter cette variable dans `.env.example` avec une valeur par défaut
  documentée pour Windows.
- `sentence-transformers` respecte-t-il `HF_HOME` ou utilise-t-il
  `TRANSFORMERS_CACHE` ?

### 3. Vérification de l'import au démarrage

À l'heure actuelle, `BGEM3Embedder` utilise un lazy loading (le modèle est
chargé au premier appel, pas à l'import). Ce comportement est correct.
Vérifier que le code dans `embedder.py` et `reranker.py` :

1. N'effectue pas d'import de `torch` ou `sentence_transformers` au niveau
   du module (ce qui ferait échouer le démarrage si PyTorch n'est pas installé).
2. Gère correctement une erreur `ImportError` si `sentence-transformers`
   n'est pas installé (cas où l'utilisateur n'a installé que les extras de base).

### 4. Compatibilité ARM Windows (Surface Pro X, Copilot+)

Les machines Windows ARM (architecture `aarch64`/`arm64`) sont de plus en plus
répandues. PyTorch propose des wheels ARM pour Windows depuis la version 2.x.
Vérifier la disponibilité et les contraintes.

### 5. Test d'import minimal

Proposer un test dans `tests/` (marqué `not integration`) qui vérifie
simplement que `sentence_transformers` peut être importé et que `BGEM3Embedder`
peut être instancié **sans** charger le modèle (lazy loading OK) :

```python
def test_embedder_instanciation():
    from kb_smart_metering.ingestion.embedder import BGEM3Embedder
    embedder = BGEM3Embedder()
    assert embedder._model is None  # pas encore chargé
```

---

## Contraintes du projet

- `sentence-transformers>=3.0.0` imposé dans `pyproject.toml`.
- Modèles `BAAI/bge-m3` et `BAAI/bge-reranker-v2-m3` imposés (configurables
  via `EMBEDDING_MODEL` et `RERANKER_MODEL` dans `.env`).
- LLM locaux uniquement (Ollama) : jamais d'appel cloud.
- Les modèles HuggingFace sont téléchargés depuis internet au premier lancement :
  c'est le comportement attendu.

---

## Livrable attendu

- Configuration `uv.toml` ou section `[tool.uv]` dans `pyproject.toml` pour
  l'index PyTorch CPU sous Windows.
- Variables à ajouter dans `.env.example` (`HF_HOME`, etc.).
- Vérification du code `embedder.py` et `reranker.py` avec éventuels diffs.
- Note dans le `README.md` section Windows sur l'installation de PyTorch et
  la taille des modèles à télécharger.
