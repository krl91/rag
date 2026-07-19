Implémente src/retrieval/.

1. search.py : recherche hybride via l'API de graphiti-core
   (recherche sémantique + BM25 + traversée de graphe). Paramètres :
   question, filtre temporel optionnel (as_of_date), filtre par type
   d'entité, top_k.
2. reranker.py : BGE-reranker-v2-m3 via sentence-transformers
   (CrossEncoder). Entrée : question + candidats ; sortie : top_n
   triés avec scores. Chargement du modèle en lazy singleton.
3. context.py : assemblage du contexte final pour le LLM :
   - budget de tokens configurable (défaut 3000),
   - regroupement par type (facts / decisions / actions / meetings),
   - chaque élément avec sa source (url, ticket, commit, fichier+page),
   - format markdown compact.
4. Gestion temporelle : si la question mentionne une version/date
   (ex : "en PR2"), filtrer les faits valides à cette date.

Tests : reranker sur cas synthétiques ; assemblage de contexte
vérifiant le respect du budget de tokens.