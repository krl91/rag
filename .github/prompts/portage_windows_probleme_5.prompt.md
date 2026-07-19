# Portage Windows — Problème 5 : Encodage UTF-8 de la console Windows

## Contexte du projet

`kb-smart-metering` est un projet en français : les docstrings, les messages
de log, les messages d'erreur et les réponses utilisateur contiennent des
caractères accentués (é, è, ê, à, ç, ù, î, ô, etc.). Le projet cible Python
3.11+ avec `logging` comme système de journalisation.

---

## Principe directeur

**Privilégier systématiquement ce qui est déjà disponible** sans configuration
supplémentaire de l'utilisateur :
- La variable d'environnement `PYTHONUTF8=1` est la solution la plus simple :
  elle peut être ajoutée dans le `.env` déjà lu par le projet (Pydantic
  Settings / python-dotenv).
- `logging.basicConfig(encoding='utf-8')` est disponible depuis Python 3.9
  (le projet exige 3.11+) — pas de dépendance supplémentaire.
- Ne pas demander à l'utilisateur de modifier des paramètres système Windows
  si une solution Python suffit.

---

## Description du problème

Sur Windows, Python 3.11–3.14 utilise l'encodage système par défaut pour la
sortie standard (`sys.stdout`) et la sortie d'erreur (`sys.stderr`).
En France/Europe, cet encodage est généralement `cp1252` (Windows-1252).

**Conséquence** : les caractères accentués dans les messages de log s'affichent
comme des `?` ou des caractères corrompus dans `cmd.exe` et PowerShell :

```
# Exemple de message attendu :
INFO:kb_smart_metering.extractors.office:Word : 12 paragraphes, 3 tableaux — rapport.docx

# Ce qui s'affiche en console Windows (cp1252) :
INFO:kb_smart_metering.extractors.office:Word : 12 paragraphes, 3 tableaux ??? rapport.docx
```

### Sources du problème

1. **`sys.stdout` / `sys.stderr`** en mode texte utilisent l'encodage système.
2. **Le handler `logging.StreamHandler`** par défaut écrit sur `sys.stderr`.
3. **`typer` / `fastapi` / `uvicorn`** peuvent eux aussi écrire sur stdout/stderr.

### Ce qui FONCTIONNE déjà

- Les fichiers source `.py` sont en UTF-8 (Python 3 par défaut).
- `config.py` lit le `.env` avec `env_file_encoding="utf-8"` (Pydantic Settings) — OK.
- `meetings.py` lit les fichiers avec `encoding="utf-8"` — OK.
- Les données stockées dans Neo4j (graphiti-core) utilisent UTF-8 nativement — OK.
- La base SQLite (`sqlite3`) utilise UTF-8 par défaut — OK.

### Ce qui pose problème

Uniquement l'**affichage** en console : les messages de log passant par
`StreamHandler` vers `sys.stderr` sans encodage explicite.

---

## Ce que tu dois analyser

### 1. Variable d'environnement `PYTHONUTF8`

Depuis Python 3.7, la variable `PYTHONUTF8=1` (ou l'option `-X utf8`) force
l'utilisation d'UTF-8 pour tous les I/O texte, quelle que soit la locale système.

- Est-ce suffisant pour ce projet ?
- Comment la documenter dans le `README.md` (section Windows) ?
- Comment l'ajouter automatiquement dans le fichier `.env.example` ?
- Y a-t-il des effets de bord indésirables sur les autres bibliothèques ?

### 2. Configuration du handler logging dans le code

Depuis Python 3.9, `logging.StreamHandler` accepte un paramètre `encoding` :

```python
handler = logging.StreamHandler()
handler.setStream(open(sys.stderr.fileno(), mode='w', encoding='utf-8', buffering=1))
```

Ou via le configurateur de logging :

```python
logging.basicConfig(
    level=logging.INFO,
    handlers=[logging.StreamHandler(stream=sys.stderr)],
    encoding="utf-8",  # Python 3.9+
)
```

- Où ce logging est-il configuré dans le projet (chercher dans `cli.py`,
  `api/app.py`, `conftest.py`) ?
- Proposer la modification minimale qui corrige l'encodage sans affecter
  Linux/macOS.

### 3. Console Windows en mode UTF-8 (`chcp 65001`)

La commande Windows `chcp 65001` passe la console en UTF-8. Est-ce une
solution viable ? Peut-elle être exécutée automatiquement ?

### 4. Recoded output pour PowerShell

PowerShell 7+ supporte `$OutputEncoding = [System.Text.Encoding]::UTF8` et
`[Console]::OutputEncoding = [System.Text.Encoding]::UTF8`. Est-ce suffisant ?

### 5. Impact sur les tests pytest

Les tests capturent-ils la sortie des logs ? Si `capsys` ou `caplog` est
utilisé dans `tests/`, y a-t-il des assertions sur des strings avec accents ?
Les tests passeraient-ils sous Windows sans modification ?

---

## Contraintes du projet

- Python 3.11+.
- `logging` (pas `print`) pour tous les messages.
- La solution doit fonctionner dans `cmd.exe`, PowerShell 5.1+ et PowerShell 7+.
- Ne pas modifier le comportement sur Linux/macOS.
- Préférer une solution automatique qui ne nécessite pas d'action manuelle
  de l'utilisateur à chaque ouverture de terminal.

---

## Livrable attendu

- La ou les modifications à apporter dans le code Python (avec diffs).
- La ligne à ajouter dans `.env.example` (si `PYTHONUTF8=1` est retenu).
- La section "Windows — Encodage" à ajouter dans `README.md`.
- Une recommandation claire sur la meilleure approche (parmi les 4 analysées).
