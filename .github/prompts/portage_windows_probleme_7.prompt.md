# Portage Windows — Problème 7 : `uvicorn[standard]` et absence de `uvloop`

## Contexte du projet

`kb-smart-metering` expose une API REST via FastAPI démarrée par `uvicorn`.
La dépendance dans `pyproject.toml` est :

```toml
"uvicorn[standard]>=0.29.0",
```

L'extra `[standard]` inclut plusieurs dépendances optionnelles d'optimisation.

---

## Principe directeur

**Privilégier systématiquement ce qui est déjà disponible** et fonctionnel :
- `uvloop` est déjà exclu automatiquement sur Windows par les markers PEP 508
  d'uvicorn — ne rien faire si c'est suffisant.
- Si `httptools` et `watchfiles` ont des wheels Windows disponibles,
  conserver `uvicorn[standard]` sans modification.
- N'intervenir sur `pyproject.toml` que si un composant de `[standard]`
  bloque réellement l'installation sous Windows.

---

## Description du problème

L'extra `[standard]` d'uvicorn inclut `uvloop`, une implémentation haute
performance de la boucle d'événements asyncio basée sur `libuv`.

**`uvloop` est incompatible avec Windows** et est exclu automatiquement via
les markers PEP 508 dans les métadonnées d'uvicorn :

```
uvloop>=0.14.0,!=0.15.0,!=0.15.1 ; sys_platform != "win32"
```

Ce qui signifie :
- Sur Linux/macOS : uvloop est installé → boucle d'événements haute performance.
- Sur Windows : uvloop n'est pas installé → boucle d'événements standard Python.

### Ce qui est inclus dans `[standard]`

L'extra `[standard]` d'uvicorn inclut également :
- `httptools` — parser HTTP rapide (C extension, peut avoir des problèmes de wheels Windows)
- `python-dotenv` — déjà dans les dépendances du projet
- `watchfiles` — rechargement automatique (développement)
- `websockets` — support WebSockets

### Vérification nécessaire

- `httptools` a-t-il des wheels Windows sur PyPI ?
- `watchfiles` a-t-il des wheels Windows ?

---

## Ce que tu dois analyser

### 1. Impact réel sur les performances

- Quantifier l'impact de l'absence d'`uvloop` sur les performances de l'API
  sous Windows : latence, throughput, scalabilité.
- Pour ce projet (usage interne, LLM local, quelques utilisateurs simultanés),
  l'absence de `uvloop` est-elle réellement problématique ?

### 2. Disponibilité des wheels Windows pour les autres composants de `[standard]`

Vérifier sur PyPI :
- `httptools` : wheels `win_amd64` disponibles ?
- `watchfiles` : wheels `win_amd64` disponibles ?

Si ces wheels manquent, `uv sync` échouera à l'installation sous Windows.

### 3. Alternatives

**Option A — Rester avec `uvicorn[standard]`**  
Si tous les composants ont des wheels Windows, pas de changement nécessaire.

**Option B — Passer à `uvicorn` sans extra**  
Remplacer `uvicorn[standard]` par `uvicorn` (sans extra) dans `pyproject.toml`.
Cela évite toute dépendance C optionnelle. Impact à documenter.

**Option C — Dépendances conditionnelles par plateforme**  
```toml
dependencies = [
    "uvicorn[standard]>=0.29.0 ; sys_platform != 'win32'",
    "uvicorn>=0.29.0 ; sys_platform == 'win32'",
]
```
Vérifier si cette syntaxe est supportée par `uv` et `hatchling`.

### 4. Configuration uvicorn pour Windows

uvicorn dispose d'options pour spécifier la boucle d'événements :
```
uvicorn --loop asyncio src.kb_smart_metering.api.app:app
```

Faut-il documenter cette option pour Windows dans le `README.md` ou dans
la commande de démarrage de l'API ?

---

## Contraintes du projet

- `fastapi>=0.111.0` et `uvicorn[standard]>=0.29.0` sont spécifiés dans
  `pyproject.toml`.
- L'API est en phase de développement (squelette) : les performances ne sont
  pas un critère prioritaire à ce stade.
- Ne pas modifier le comportement sur Linux/macOS.

---

## Livrable attendu

- Rapport de disponibilité des wheels Windows pour `httptools` et `watchfiles`.
- Recommandation : conserver `[standard]` ou non ?
- Si changement recommandé : diff dans `pyproject.toml`.
- Note dans le `README.md` expliquant les différences de performance Windows
  vs Linux/macOS pour l'API.
