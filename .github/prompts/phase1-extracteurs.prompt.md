Implémente les extracteurs dans src/extractors/. Un module par source.

Modèle intermédiaire commun (src/normalize/models.py) :
- RawDocument : id_source, source_type (jira|confluence|git|docx|xlsx|
  pdf|meeting|obsidian), titre, contenu_texte, auteur, date_creation,
  date_modification, url_ou_chemin, metadonnees (dict), pieces_jointes.

Extracteurs à livrer, dans cet ordre :
1. jira.py : tickets d'un projet (JQL configurable), commentaires,
   historique de statuts, liens entre tickets. Pagination gérée.
2. confluence.py : pages d'un espace, corps en texte (conversion du
   storage format), commentaires, historique de versions.
3. git.py : commits (message, auteur, fichiers touchés), branches,
   tags/releases d'un dépôt local cloné.
4. office.py : Word (python-docx : paragraphes + tableaux + titres),
   Excel (openpyxl : une entrée par feuille, tableaux → markdown),
   PDF (pymupdf : texte par page, conserver numéro de page).
5. meetings.py : parseur de transcriptions (txt/vtt) → segments
   horodatés + participants détectés.

Chaque extracteur : une classe avec extract() -> list[RawDocument],
gestion d'erreurs explicite, log du volume extrait.
Tests pytest avec fixtures locales (fichiers d'exemple dans
tests/fixtures/), API mockées.

Interdit dans cette phase : ingestion Graphiti, appels LLM.