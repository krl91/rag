Implémente src/revengine/.

1. ast_extract.py : tree-sitter (Java, Python, C# — configurable) :
   classes, méthodes, interfaces, appels sortants, événements
   publiés/consommés (heuristiques sur les noms *Event, publish,
   subscribe), modèles de données.
2. graph_build.py : transforme ces éléments en RawDocument +
   relations candidates (Component --publie--> Event,
   Component --appelle--> Component) pour ingestion Phase 2.
3. docgen.py : génération de documentation fonctionnelle Markdown/
   Obsidian par module : description métier (via LLM local, contexte
   = éléments du graphe du module uniquement), composants, flux,
   règles métier détectées, sources (fichiers + lignes).
4. CLI : `kb reveng --repo ./chemin --lang java`,
   `kb docgen --module Export --out docs/`.

Chaque appel LLM : petit périmètre (1 module max), réponse structurée.