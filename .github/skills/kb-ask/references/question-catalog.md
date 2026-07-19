# Catalogue de questions — kb-smart-metering

> **Ces exemples supposent un LLM réseau joignable (Ollama) et `uv`
> disponible.** Sans LLM réseau (flux par défaut, voir skill `kb-ask`) :
> remplacer chaque `uv run kb ask "..."` par `kb search "..."` — la
> commande affiche le contexte pertinent, à toi (l'agent) de rédiger la
> réponse à partir de ce contexte uniquement. Sans `uv` (Windows, py+pip) :
> remplacer `uv run kb` par `kb` (venv activé) ou `py -m
> kb_smart_metering.cli`. Les questions elles-mêmes restent valables dans
> les deux cas.

## Décisions et arbitrages

```bash
# Décisions générales
uv run kb ask "Quelles décisions d'architecture ont été prises sur le module Export ?"
uv run kb ask "Pourquoi a-t-on choisi Kafka plutôt que RabbitMQ ?"
uv run kb ask "Qui a validé la décision sur le protocole DLMS ?"
uv run kb ask "Quelles décisions ont été prises en PR2 sur l'intégration MDM ?"

# Décisions par composant
uv run kb ask "Quelles décisions concernent le concentrateur de données ?"
uv run kb ask "Quel protocole de communication a été retenu pour les compteurs ?"
uv run kb ask "Quelle base de données a été choisie pour le service de relevé ?"
```

## Suivi d'actions

```bash
# Actions ouvertes
uv run kb ask "Quelles actions sont assignées à l'équipe architecture ?"
uv run kb ask "Quelles actions du sprint 2 n'ont pas été clôturées ?"
uv run kb ask "Quelles actions ont été assignées à Pierre Martin ?"

# Actions par thème
uv run kb ask "Quelles actions concernent la performance du concentrateur ?"
uv run kb ask "Quelles actions de sécurité sont en attente ?"

# Tickets Jira
uv run kb ask "Quels tickets SMART sont en statut bloqué ?"
uv run kb ask "Quels tickets concernent la performance de l'API de relevé ?"
uv run kb ask "Quel est le statut du ticket SMART-142 ?"
```

## Risques et dépendances

```bash
# Risques identifiés
uv run kb ask "Quels sont les risques identifiés sur l'intégration MDM ?"
uv run kb ask "Y a-t-il des dépendances critiques non résolues ?"
uv run kb ask "Quels risques techniques ont été soulevés en sprint review ?"

# Dépendances
uv run kb ask "De quels systèmes externes dépend le service de facturation ?"
uv run kb ask "Quelles équipes sont impliquées dans la livraison du module Export ?"
```

## Architecture et technique

```bash
# Flux et interfaces
uv run kb ask "Comment fonctionne l'interface entre le compteur et le concentrateur ?"
uv run kb ask "Quelle version de l'API expose le service de relevé ?"
uv run kb ask "Quels composants consomment l'événement MeterReadingReceived ?"
uv run kb ask "Quel est le flux de données entre le MDM et le système de facturation ?"

# Composants et applications
uv run kb ask "Quelles applications constituent le périmètre smart metering ?"
uv run kb ask "Quels microservices composent la plateforme de collecte ?"
uv run kb ask "Quelle technologie est utilisée pour le bus de messages ?"

# Historique de version
uv run kb ask "Quelles fonctionnalités ont été livrées dans la version 2.3.0 ?"
uv run kb ask "Quels composants ont évolué entre PR1 et PR2 ?"
```

## Réunions et historique

```bash
# Réunions spécifiques
uv run kb ask "Qu'a-t-on décidé lors de la réunion du 15 janvier 2024 ?"
uv run kb ask "Qui était présent à la réunion de lancement de PR3 ?"
uv run kb ask "Quels sujets ont été abordés dans les réunions de sprint review ?"

# Pages Confluence
uv run kb ask "Quelle est la dernière mise à jour de la page d'architecture ?"
uv run kb ask "Que dit la page Confluence sur le protocole DLMS ?"

# Personnes
uv run kb ask "Quel est le rôle de Sophie Dupont dans le projet ?"
uv run kb ask "Qui est l'architecte responsable du module concentrateur ?"
```

## Questions temporelles — par phase

```bash
# PR1 — juin 2023
uv run kb ask "Quelles décisions d'architecture ont été prises en PR1 ?"

# PR2 — décembre 2023
uv run kb ask "Quelle était l'architecture de communication en PR2 ?"
uv run kb ask "Quels risques ont été identifiés en PR2 ?"

# PR3 — juin 2024
uv run kb ask "Quels nouveaux composants ont été introduits en PR3 ?"

# Comparaison entre phases
uv run kb ask "Comment l'architecture a-t-elle évolué entre PR1 et PR3 ?"
uv run kb ask "Quelles décisions de PR2 ont été remises en question en PR3 ?"
```

## Questions de synthèse (usage réunion)

```bash
# Préparation d'un comité d'architecture
uv run kb ask "Quelles décisions d'architecture importantes ont été prises ces 3 derniers mois ?"
uv run kb ask "Quels sujets techniques sont en discussion ou non résolus ?"
uv run kb ask "Quelles règles métier impactent le module de facturation ?"

# Préparation d'un sprint planning
uv run kb ask "Quelles actions ouvertes doivent être priorisées ?"
uv run kb ask "Quels tickets Jira ont des dépendances bloquantes ?"
uv run kb ask "Quels risques techniques nécessitent une attention particulière ?"
```
