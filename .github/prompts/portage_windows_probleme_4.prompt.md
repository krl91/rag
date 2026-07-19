# Portage Windows — Problème 4 : Chemins Windows dans les clés d'épisodes SQLite

## Contexte du projet

`kb-smart-metering` maintient une base SQLite (`data/ingestion_tracking.db`)
pour assurer l'idempotence de l'ingestion. Chaque document ingéré est
identifié par une clé `episode_key` unique construite à partir de l'ID de la
source, du type de source et d'une version.

---

## Principe directeur

**Privilégier systématiquement ce qui est déjà disponible** dans le projet :
- `pathlib.Path` (déjà utilisé partout dans le projet) expose `as_posix()`,
  `as_uri()` et `relative_to()` — exploiter ces méthodes en priorité.
- `hashlib` (déjà importé dans `pipeline.py`) peut être utilisé pour
  normaliser les IDs sans dépendance supplémentaire.
- Éviter d'ajouter une bibliothèque tierce pour un problème de normalisation
  de chaîne de caractères soluble avec la stdlib.

---

## Description du problème

### Construction de la clé `episode_key`

Dans `src/kb_smart_metering/ingestion/pipeline.py`, la clé est construite ainsi :

```python
@staticmethod
def _episode_key(doc: RawDocument) -> str:
    if doc.date_modification:
        version = doc.date_modification.isoformat()
    else:
        version = hashlib.sha256(doc.contenu_texte.encode()).hexdigest()[:16]
    return f"{doc.source_type}:{doc.id_source}:{version}"
```

### Construction de `id_source` pour les fichiers locaux

Dans `src/kb_smart_metering/extractors/office.py` (et `meetings.py`) :

```python
RawDocument(
    id_source=str(self._file_path.resolve()),   # ← PROBLÈME
    ...
    url_ou_chemin=str(self._file_path.resolve()),
)
```

### Le problème sur Windows

Sur macOS/Linux, `str(Path(...).resolve())` retourne `/home/user/docs/fichier.docx`.

Sur Windows, cela retourne `C:\Users\karelredon\docs\fichier.docx`.

La clé `episode_key` générée devient alors :

```
docx:C:\Users\karelredon\docs\fichier.docx:2024-01-15T10:30:00+00:00
```

Ce format est problématique pour plusieurs raisons :

1. **Ambiguïté du séparateur `:`** : le format attendu est
   `{source_type}:{id_source}:{version}`, mais sur Windows `id_source` contient
   déjà des `:` (`C:`). Si une fonction parse cette clé en splitant sur `:`,
   elle obtient 4+ parties au lieu de 3.

2. **Cohérence entre plateformes** : si la base SQLite est copiée d'un système
   Linux vers un Windows (ou inversement), les clés ne seront jamais retrouvées,
   cassant l'idempotence.

3. **Backslashes dans les logs** : `C:\Users\...` contient des `\` qui sont
   des caractères d'échappement dans certains contextes (JSON, regex), causant
   des confusions dans les logs et les messages d'erreur.

### Fichiers concernés

- `src/kb_smart_metering/ingestion/pipeline.py` — méthode `_episode_key()`
- `src/kb_smart_metering/extractors/office.py` — `WordExtractor`, `ExcelExtractor`, `PdfExtractor`
- `src/kb_smart_metering/extractors/meetings.py` — `MeetingExtractor`
- `src/kb_smart_metering/normalize/models.py` — modèle `RawDocument`

---

## Ce que tu dois analyser

### 1. Stratégie de normalisation de `id_source`

Plusieurs approches sont envisageables. Analyser et comparer :

**Option A — Utiliser `Path.as_posix()`**  
Convertit les backslashes en slashes : `C:/Users/karelredon/docs/fichier.docx`.
Réduit les backslashes mais conserve le `C:` problématique.

**Option B — Chemin relatif depuis la racine du projet**  
`id_source = str(self._file_path.resolve().relative_to(Path.cwd()))` ou
relative à un répertoire de base configuré. Portable et stable.
Problème : si le fichier est hors du projet, `relative_to()` lève une exception.

**Option C — Hash SHA-256 du chemin absolu normalisé**  
`id_source = hashlib.sha256(str(path.resolve()).lower().encode()).hexdigest()`
Garantit l'unicité sans exposer le chemin. Perd la lisibilité humaine.

**Option D — Changer le séparateur de la clé**  
Utiliser `|` ou `::` comme séparateur dans `_episode_key()` à la place de `:`.
Simple mais change le format de toutes les clés existantes (migration nécessaire).

**Option E — URI de fichier**  
`id_source = self._file_path.resolve().as_uri()`
Retourne `file:///C:/Users/...` sur Windows, `file:///home/...` sur Linux.
Format standard, mais les `/` sont déjà présents dans le schéma `file://`.

### 2. Impact sur la base SQLite existante

- Si le format de `episode_key` change, les épisodes déjà ingérés ne seront
  plus retrouvés → double ingestion. Comment gérer la migration ?
- Faut-il une version de schéma dans la base (`schema_version`) ?

### 3. Vérification des usages de `episode_key`

Inspecter tout le code pour trouver les endroits où `episode_key` est parsé
(splitté par `:`). Si aucun code ne parse la clé, le problème est limité.

### 4. Normalisation de `url_ou_chemin`

Le champ `url_ou_chemin` de `RawDocument` est utilisé comme référence source
dans les réponses du LLM (`{sources}` dans `LLMResponse`). Les backslashes
Windows dans les chemins affichés à l'utilisateur sont illisibles.
Doit-il être normalisé en URI `file:///` ou en chemin POSIX ?

---

## Contraintes du projet

- Pydantic v2 pour `RawDocument` (champ `id_source: str`).
- L'idempotence est garantie par `episode_key` + `content_hash` dans SQLite.
- Ne pas modifier le schéma de la base SQLite sans fournir une migration.
- `graphiti-core` reçoit `episode_key` comme identifiant d'épisode — vérifier
  les contraintes de format acceptées par Graphiti.

---

## Livrable attendu

- Recommandation d'une option (A–E) avec justification.
- Le diff exact à appliquer dans chaque fichier concerné.
- Si une migration SQLite est nécessaire : le script de migration à inclure dans
  `scripts/migrate_episode_keys.py`.
- Tests unitaires à ajouter dans `tests/test_ingestion.py` pour valider le
  comportement sous des chemins Windows simulés (via `pathlib.PureWindowsPath`
  dans les fixtures).
