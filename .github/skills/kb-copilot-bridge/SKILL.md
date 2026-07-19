---
name: kb-copilot-bridge
description: "Option AVANCÉE et déconseillée par défaut : configuration du pont VS Code Copilot Bridge (serveur HTTP local, port 4141) comme LLM dans kb-smart-metering. Le flux recommandé sans Ollama est le flux conversationnel (skills kb-ingest/kb-ask, sans serveur ni port) — n'utiliser ce skill que si un pipeline LLM automatique en une commande est explicitement requis malgré l'ouverture d'un port local."
argument-hint: "Port du pont (défaut 4141) et famille de modèle (défaut gpt-4o)"
---

# Skill — Pont Copilot (option avancée, déconseillée par défaut)

> **Par défaut, n'utilise pas ce skill.** Sur une machine sans Ollama, le
> flux recommandé est le **flux conversationnel** (skills `kb-ingest` /
> `kb-ask`) : aucun serveur, aucun port ouvert, tout se passe dans cette
> conversation VS Code. Le pont décrit ici ouvre un serveur HTTP local
> (port 4141) — à réserver aux cas où un pipeline LLM automatique en une
> seule commande (`kb ingest`/`kb ask` sans intervention de l'agent) est
> explicitement demandé, en connaissance du compromis sécurité (port local
> ouvert, même en loopback).

## Quand utiliser ce skill malgré tout

- Un pipeline d'ingestion/réponse automatique en une commande est requis
  (pas de tour de conversation par document), et Ollama n'est pas disponible
- L'utilisateur a explicitement accepté le compromis "port local ouvert"
- **Ne pas confondre avec GitHub Models** : ce service (endpoint
  `models.github.ai`) a été retiré par GitHub le 30/07/2026 et n'est plus
  utilisable. Le pont décrit ici passe par l'API publique `vscode.lm`
  (extension VS Code), pas par l'API GitHub Models.

---

## Principe

Une extension VS Code locale (`copilot-bridge/`, à la racine du dépôt)
démarre un petit serveur HTTP sur `127.0.0.1` qui traduit les appels
`POST /v1/chat/completions` (format OpenAI, ce que `kb_smart_metering`
envoie déjà) vers l'API `vscode.lm`, laquelle relaie vers le modèle
sélectionné dans GitHub Copilot Chat.

```
kb_smart_metering (Python)  →  http://127.0.0.1:4141/v1/chat/completions
                                          │
                                 extension copilot-bridge (VS Code)
                                          │
                                   vscode.lm.sendRequest()
                                          │
                                   GitHub Copilot Chat
```

Aucune modification du code Python n'est nécessaire : `OLLAMA_BASE_URL`,
`OLLAMA_MODEL` et `LLM_API_KEY` restent les seules variables à changer,
exactement comme pour basculer vers un autre Ollama.

> **Limite essentielle** : ce pont n'est **pas un service headless**. Il ne
> répond que si VS Code est ouvert, l'extension chargée et le pont démarré
> (commande palette). Il n'y a pas d'ingestion planifiée (cron) sans session
> VS Code active — voir `copilot-bridge/README.md`.

> **Confidentialité** : les questions et extraits de contexte transitent par
> Copilot Chat (infrastructure GitHub/Microsoft). Ne pas utiliser avec des
> données très confidentielles selon votre politique de sécurité — le même
> avertissement que pour tout LLM cloud s'applique.

> **Quota** : chaque appel (ingestion Phase 2 comme `kb ask`) consomme le
> quota Copilot de l'utilisateur au même titre qu'un message tapé dans le
> chat. Une ingestion en masse (dizaines de tickets/pages) peut consommer un
> volume de requêtes significatif — préférer des lots réduits et incrémentaux
> (`--updated-since`) plutôt qu'une ingestion initiale massive.

---

## Étape 1 — Installer et démarrer l'extension

Prérequis : [Node.js](https://nodejs.org/) 20+ sur la machine.

```powershell
cd copilot-bridge
npm install
npm run compile
```

Deux façons de la charger dans VS Code :

- **Développement** : ouvrir le dossier `copilot-bridge/` dans VS Code et
  appuyer sur **F5** (ouvre une fenêtre "Extension Development Host").
- **Usage quotidien** : empaqueter une fois et installer durablement :
  ```powershell
  npx vsce package
  code --install-extension kb-copilot-bridge-0.1.0.vsix
  ```

Puis, dans la fenêtre où l'extension est active : palette de commandes
(`Ctrl+Shift+P`) → **"KB Bridge: Démarrer le pont Copilot"**. La barre de
statut affiche `KB Bridge :4141` une fois démarré.

---

## Étape 2 — Configurer `.env`

```dotenv
# Commenter la configuration Ollama
# OLLAMA_BASE_URL=http://localhost:11434/v1
# OLLAMA_MODEL=mistral:7b

# Activer le pont Copilot
OLLAMA_BASE_URL=http://127.0.0.1:4141/v1
OLLAMA_MODEL=gpt-4o
# LLM_API_KEY=          ← laisser vide : pont local sans authentification
```

---

## Modèles disponibles

Dépend des modèles exposés par l'abonnement Copilot de l'utilisateur dans
VS Code (`vendor: "copilot"`). Typiquement : `gpt-4o`, `gpt-4o-mini`,
`claude-3.5-sonnet`. Vérifier la liste réellement disponible :

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:4141/v1/models"
```

---

## Étape 3 — Vérifier la connexion

**PowerShell (Windows) :**
```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:4141/health"

Invoke-RestMethod `
  -Uri "http://127.0.0.1:4141/v1/chat/completions" `
  -Method POST `
  -ContentType "application/json" `
  -Body '{"model":"gpt-4o","messages":[{"role":"user","content":"ping"}]}'
```

**bash (macOS/Linux, si le pont est testé hors Windows) :**
```bash
uv run python -c "
import httpx, os
from dotenv import load_dotenv
load_dotenv()
r = httpx.post(
    os.getenv('OLLAMA_BASE_URL') + '/chat/completions',
    json={'model': os.getenv('OLLAMA_MODEL'), 'messages': [{'role':'user','content':'ping'}]},
    timeout=30
)
print(r.status_code, r.json()['choices'][0]['message']['content'])
"
```

---

## Basculer entre Ollama et le pont Copilot

Le basculement se fait uniquement dans `.env` — aucun changement de code.

```dotenv
# ─── OLLAMA (local) ────────────────────────────────────────────
OLLAMA_BASE_URL=http://localhost:11434/v1
OLLAMA_MODEL=mistral:7b
# LLM_API_KEY=          ← laisser vide ou absent

# ─── PONT COPILOT (VS Code + extension copilot-bridge) ────────
# OLLAMA_BASE_URL=http://127.0.0.1:4141/v1
# OLLAMA_MODEL=gpt-4o
# LLM_API_KEY=           ← laisser vide, pont local sans authentification
```

> **Note** : les embeddings (BGE-M3) et le reranker restent toujours locaux
> via `sentence-transformers`, quelle que soit la configuration LLM.

---

## Diagnostics courants

| Symptôme | Cause probable | Solution |
|---|---|---|
| `Connection refused` sur `127.0.0.1:4141` | Extension pas démarrée | Palette de commandes → "KB Bridge: Démarrer le pont Copilot" |
| `Aucun modèle Copilot "gpt-4o" disponible` | Abonnement Copilot inactif ou modèle non autorisé | Vérifier l'abonnement, essayer `gpt-4o-mini` |
| Ingestion très lente / erreurs intermittentes | Quota Copilot atteint | Réduire la taille des lots, espacer les runs `kb ingest` |
| Le pont s'arrête tout seul | Fenêtre VS Code fermée | Le pont vit dans le process VS Code ; garder la fenêtre ouverte pendant l'ingestion |
