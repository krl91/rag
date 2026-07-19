# Portage Windows — Problème 6 : `tree-sitter-language-pack` et wheels binaires Windows

## Contexte du projet

`kb-smart-metering` inclut un module `revengine` (rétro-ingénierie de code
source) qui analyse des dépôts Java, Python et C# via `tree-sitter`.
Les dépendances concernées sont :

```toml
"tree-sitter>=0.22.0",
"tree-sitter-language-pack>=0.0.1",
```

---

## Principe directeur

**Privilégier systématiquement ce qui est déjà disponible** comme wheels
binaires sur PyPI, sans exiger l'installation d'un compilateur C :
- Vérifier en premier si `tree-sitter` et `tree-sitter-language-pack` ont des
  wheels Windows prêts à l'emploi pour la version requise (>=0.22.0).
- Si des wheels existent, aucune action n'est nécessaire : documenter
  simplement la compatibilité.
- N'envisager une migration vers des paquets alternatifs ou une mise en
  dépendance optionnelle que si les wheels sont réellement absents.
- Si un compilateur C est déjà présent (Visual Studio Build Tools), l'utiliser
  avant de chercher une alternative.

---

## Description du problème

`tree-sitter` et `tree-sitter-language-pack` sont des paquets Python qui
wrappent des bibliothèques C compilées. Lors de l'installation via `pip` / `uv`,
Python cherche un **wheel binaire pré-compilé** pour la plateforme cible.
Si aucun wheel n'existe, il tente une compilation depuis les sources, ce qui
nécessite un **compilateur C** (MSVC sur Windows ou MinGW/Clang).

### Vérification de la disponibilité des wheels

Vérifier sur PyPI si des wheels sont disponibles pour :
- `tree-sitter>=0.22.0` : <https://pypi.org/project/tree-sitter/#files>
- `tree-sitter-language-pack>=0.0.1` : <https://pypi.org/project/tree-sitter-language-pack/#files>

Les plateformes à vérifier :
- `win_amd64` (Windows 64-bit x86)
- `win_arm64` (Windows ARM, Surface Pro X, etc.)
- `cp311`, `cp312`, `cp313` (versions Python)

### Code concerné

Le module `src/kb_smart_metering/revengine/ast_extract.py` importe :

```python
# (import dynamique à l'intérieur des méthodes, à vérifier dans le code)
from tree_sitter import Language, Parser
```

Et `tree-sitter-language-pack` fournit les grammaires pré-compilées pour
Java, Python, C#.

---

## Ce que tu dois analyser

### 1. État actuel des wheels Windows

Inspecter PyPI pour `tree-sitter` et `tree-sitter-language-pack` :
- Des wheels `win_amd64` sont-ils disponibles pour Python 3.11+ ?
- Des wheels `win_arm64` sont-ils disponibles ?
- Quelle est la version minimale qui dispose de wheels Windows ?

### 2. Compilation depuis les sources (fallback)

Si aucun wheel n'est disponible :
1. Quels outils sont nécessaires pour compiler `tree-sitter` sous Windows ?
   - Visual Studio Build Tools (MSVC) ?
   - MinGW-w64 ?
   - Clang pour Windows ?
2. Ces outils peuvent-ils être installés sans droits d'administrateur ?
3. `uv sync` gère-t-il automatiquement la compilation des extensions C ?

### 3. Alternatives à `tree-sitter-language-pack`

`tree-sitter-language-pack` est un paquet tiers qui bundle de nombreuses
grammaires. Des alternatives officielles existent :
- `tree-sitter-java` (paquet officiel de la grammaire Java)
- `tree-sitter-python` (grammaire Python)
- `tree-sitter-c-sharp` (grammaire C#)

Ces paquets officiels ont-ils de meilleures garanties de wheels Windows ?
Le code de `ast_extract.py` doit-il être modifié pour utiliser ces alternatives ?

### 4. Chargement dynamique dans `ast_extract.py`

tree-sitter >= 0.22.0 a changé son API (les grammaires sont maintenant des
bindings Python plutôt que des fichiers `.so` chargés dynamiquement).
Vérifier que le code dans `ast_extract.py` utilise bien la nouvelle API :

```python
# Ancienne API (<0.22) — NE FONCTIONNE PAS avec la version imposée
Language.build_library("my-languages.so", ["vendor/tree-sitter-java"])

# Nouvelle API (>=0.22)
import tree_sitter_java
language = Language(tree_sitter_java.language())
```

L'API utilisée dans `ast_extract.py` est-elle compatible avec `>=0.22.0` et
avec Windows ?

### 5. Isolation dans une dépendance optionnelle

Le module `revengine` n'est pas critique pour les fonctionnalités de base
(ingestion, retrieval, API). Envisager de le rendre optionnel :

```toml
[project.optional-dependencies]
revengine = [
    "tree-sitter>=0.22.0",
    "tree-sitter-language-pack>=0.0.1",
]
```

Avec une vérification à l'import :

```python
try:
    from tree_sitter import Language, Parser
except ImportError:
    raise ImportError(
        "Le module revengine nécessite tree-sitter. "
        "Installer avec : uv sync --extra revengine"
    )
```

---

## Contraintes du projet

- `tree-sitter>=0.22.0` est spécifié dans `pyproject.toml`.
- Les langages analysés sont Java, Python et C# (voir `Language` enum dans
  `ast_extract.py`).
- Les tests dans `tests/test_revengine.py` ne doivent pas nécessiter de
  compilateur C pour s'exécuter.

---

## Livrable attendu

- Rapport sur la disponibilité des wheels Windows pour chaque paquet.
- Si des alternatives sont nécessaires : le diff dans `pyproject.toml`.
- Si le code `ast_extract.py` doit être modifié pour la nouvelle API ou les
  paquets alternatifs : le diff complet.
- Recommandation sur la mise en dépendance optionnelle (avec diff dans
  `pyproject.toml` et modification des imports dans `ast_extract.py`).
- Instructions d'installation Windows dans le `README.md`.
