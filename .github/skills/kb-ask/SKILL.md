---
name: kb-ask
description: "Interroger la base de connaissances kb-smart-metering en langage naturel, entièrement dans la conversation VS Code (aucun serveur, aucun LLM réseau requis). Utiliser pour : trouver des décisions d'architecture, lister des actions ou risques, retrouver des informations de réunion, poser des questions datées sur une phase ou sprint (PR1-PR4, sprint1-sprint4), filtrer par type d'entité (Decision, Action, Risk, Person, Application, Component). Récupère le contexte pertinent puis TOI (l'agent) rédiges la réponse."
argument-hint: "Question, domaine (décisions|actions|risques|architecture|réunions) ou phase (PR2, sprint3)"
---

# Skill — Interroger la base de connaissances (flux conversationnel, sans LLM réseau)

## Principe

`kb search` fait uniquement le retrieval (recherche graphe + vecteurs +
reranking, 100 % local via sentence-transformers) et affiche le contexte
pertinent — **sans jamais appeler de LLM réseau**. C'est ensuite TOI, dans
cette conversation, qui rédiges la réponse structurée à partir de ce
contexte, exactement comme le ferait le LLM local dans l'ancien pipeline.

```
[kb search "question"]     [TOI : rédaction de la réponse]
Python — retrieval seul →   à partir UNIQUEMENT du contexte affiché
(aucun LLM)                  (ton travail de synthèse)
```

---

## Étape 1 — Récupérer le contexte (Python, aucun LLM)

```bash
py -m kb_smart_metering.cli search "Pourquoi supprime-t-on l'export Missing Data pour Unity Water ?"
```

(Sur une machine avec `uv`, `uv run kb search "..."` fonctionne aussi de façon équivalente.)

Options :
```bash
py -m kb_smart_metering.cli search "quelle architecture en PR2 ?" --as-of 2023-12-01
py -m kb_smart_metering.cli search "décisions" --type Decision,Action
```

La commande affiche le contexte assemblé (faits, décisions, réunions… avec
leurs sources) — ou `"Aucun contexte disponible dans le graphe de
connaissances."` si rien n'a été trouvé.

---

## Étape 2 — Rédiger la réponse (TON travail, dans la conversation)

À partir **uniquement** du contexte affiché par `kb search`, rédige une
réponse structurée :

```json
{
  "resume":    "Résumé de la réponse en une phrase",
  "facts":     ["Fait 1", "Fait 2"],
  "decisions": ["Décision identifiée"],
  "actions":   ["Action assignée à X"],
  "risks":     ["Risque sur composant Y"],
  "sources":   ["SMART-142", "ARCH/Integration", "reunion_2024-01-15.txt"]
}
```

Règles impératives (identiques à l'ancien prompt système du LLM local) :
- Réponds **uniquement** à partir du contexte fourni par `kb search`.
- Si l'information est absente du contexte, **dis-le explicitement** —
  n'invente jamais une réponse plausible.
- Cite les sources telles qu'elles apparaissent dans le contexte.
- Présente la réponse à l'utilisateur de façon lisible (pas le JSON brut),
  avec sections **Résumé / Décisions / Actions / Risques / Sources**.

---

## Filtres temporels automatiques

`kb search` reconnaît les phases projet directement dans la question :

```bash
py -m kb_smart_metering.cli search "Quelle était l'architecture en PR2 ?"          # filtre → déc 2023
py -m kb_smart_metering.cli search "Quelles décisions ont été prises au sprint 3 ?" # filtre → sept 2023
```

Phases reconnues : `PR1` (juin 2023), `PR2` (déc 2023), `PR3` (juin 2024),
`PR4` (déc 2024), `sprint1`–`sprint4`.

---

## Alternative — si Ollama (ou un endpoint LLM local) est disponible

Si `.env` pointe vers un LLM réseau réellement joignable, `kb ask` fait tout
en une commande (retrieval + réponse générée par ce LLM, sans passer par toi) :

```bash
uv run kb ask "votre question en langage naturel"
```

N'utilise cette voie que si un LLM réseau est confirmé joignable — sinon
elle échoue avec une erreur de connexion. Dans le doute, utilise `kb search`
+ ta propre rédaction ci-dessus, qui fonctionne toujours.

---

## Questions types par domaine

Voir [question-catalog.md](./references/question-catalog.md) pour le catalogue
complet avec 40+ exemples organisés par domaine (décisions, actions, risques,
architecture, réunions, multi-projet) — remplacer `kb ask` par `kb search`
dans les exemples si aucun LLM réseau n'est disponible.

---

## Conseils pour des questions efficaces

| À faire | À éviter |
|---|---|
| Questions précises avec contexte | Questions vagues ("dis-moi tout") |
| Mentionner phase/sprint | Questions hors périmètre |
| Utiliser les noms exacts des composants | Demander des documents complets |
| Citer le type attendu (décision, action…) | Questions hypothétiques générales |

> Si le contexte retourné par `kb search` est vide : la source n'a
> probablement pas été ingérée. Utiliser `/kb-ingest` puis réessayer.
