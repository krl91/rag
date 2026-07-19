"""
Package extracteurs — responsable de la collecte des données brutes depuis
chaque source (Jira, Confluence, Git, fichiers locaux, réunions).

Chaque sous-module implémente un extracteur dédié qui retourne des objets
Pydantic normalisés, prêts pour l'ingestion dans Graphiti.
"""
