# Configuration

OCAPI charge sa configuration depuis deux endroits :

- les variables d'environnement (et un fichier `.env`) via **Pydantic Settings**
  (clés API, chemins, logging) ;
- trois fichiers JSON sous `config/` pour le LLM (modèle, résilience, rate
  limit), versionnés dans le repo.

## Fichier `.env`

Copier le template puis renseigner les valeurs nécessaires :

```bash
cp .env.example .env
```

Le préfixe `LLM__` correspond au champ `llm` de la config Pydantic. Le
séparateur `__` permet de cibler un sous-objet (`env_nested_delimiter="__"`
dans [`ocapi/config.py`](https://github.com/mte-dgpr/ocapi/blob/main/ocapi/config.py)).

## Variables d'environnement

### LLM (`LLMConfig`)

| Variable | Type | Défaut | Notes |
|---|---|---|---|
| `LLM__PIAG_API_KEY` | `str \| None` | `None` | Clé API PIAG (MTE). |
| `LLM__PIAG_API_URL` | `str` | `https://preprod.api.piag.e2.rie.gouv.fr/v1/chat/completions` | |
| `LLM__MISTRAL_API_KEY` | `str \| None` | `None` | |
| `LLM__MISTRAL_API_URL` | `str` | `https://api.mistral.ai/v1/chat/completions` | |
| `LLM__OPENAI_API_KEY` | `str \| None` | `None` | |
| `LLM__OPENAI_API_URL` | `str` | `https://api.openai.com/v1/chat/completions` | |
| `LLM__ANTHROPIC_API_KEY` | `str \| None` | `None` | |
| `LLM__ANTHROPIC_API_URL` | `str` | `https://api.anthropic.com/v1/messages` | |
| `LLM__GOOGLE_API_KEY` | `str \| None` | `None` | |
| `LLM__GOOGLE_API_URL` | `str` | `…/v1beta/openai/chat/completions` | Endpoint compatible OpenAI. |
| `LLM__DEEPSEEK_API_KEY` | `str \| None` | `None` | |
| `LLM__DEEPSEEK_API_URL` | `str` | `https://api.deepseek.com/v1/chat/completions` | |

Aucune clé n'est requise au démarrage. Les vérifications se font au moment de
l'appel pour le provider sélectionné dans `config/llm_models.json`.

### Chemins (`PathsConfig`)

| Variable | Type | Défaut | Notes |
|---|---|---|---|
| `PATHS__PROJECT_ROOT` | `Path` | parent du package `ocapi/` | Doit exister, sert de base aux chemins relatifs. |
| `PATHS__CATALOGUE_PATH` | `Path` | `data/0005804239/journaux/catalogue_ap.json` | Optionnel. |
| `PATHS__PERMIS_TEMPLATE_PATH` | `Path` | `templates/permis_consolide.html` | Doit exister, contient `{{HEADER}}`, `{{CONTENT}}`, `{{OTHER}}`. |
| `PATHS__INPUT_DIR` | `Path \| None` | `None` | |
| `PATHS__OUTPUT_FILE` | `Path \| None` | `None` | |

### Logging (`LoggingConfig`, préfixe `LOG_`)

| Variable | Type | Défaut |
|---|---|---|
| `LOG_LEVEL` | `DEBUG` / `INFO` / `WARNING` / `ERROR` / `CRITICAL` | `INFO` |
| `LOG_LOG_FILE` | `Path \| None` | `None` |
| `LOG_MAX_BYTES` | `int` (≥ 1024) | `1048576` (1 Mio) |
| `LOG_BACKUP_COUNT` | `int` (0–100) | `5` |
| `LOG_USE_TIMED_ROTATION` | `bool` | `true` |
| `LOG_CONSOLE_OUTPUT` | `bool` | `true` |

## Fichiers `config/`

Les paramètres LLM sont versionnés (pas de secrets). Voir [LLM](llm.md) pour
le détail de chaque champ.

### `config/llm_models.json`

Choisit le modèle primaire (et secondaire optionnel) parmi les modèles
déclarés. Exemple courant :

```json
{
  "primary_model_key": "openai_gpt5nano",
  "secondary_model_key": null,
  "models": {
    "openai_gpt5mini": { "provider": "openai", "model_id": "gpt-5-mini", "reasoning_model": true },
    "openai_gpt5nano": { "provider": "openai", "model_id": "gpt-5-nano", "reasoning_model": true },
    "mistral_medium": { "provider": "mistral", "model_id": "mistral-medium-latest" },
    "piag_mistral_medium": { "provider": "mte-piag", "model_id": "mte-api-piag-mistral-medium-latest" },
    "deepseek_4-pro": { "provider": "deepseek", "model_id": "deepseek-v4-pro" }
  }
}
```

Providers supportés : `mte-piag`, `mistral`, `openai`, `anthropic`, `google`, `deepseek`.
`reasoning_model: true` change le payload OpenAI (passe `reasoning_effort: high`
+ `verbosity: low` au lieu de `temperature`).

`primary_model_key` et `secondary_model_key` peuvent être surchargés sans
toucher au JSON via les variables d'environnement `LLM_PRIMARY_MODEL_KEY` et
`LLM_SECONDARY_MODEL_KEY` (la valeur doit correspondre à une `model_key`
déclarée dans `models`).

### `config/llm_resilience.json`

```json
{
  "fallback_enabled": false,
  "timeout_seconds": 120,
  "retry": {
    "primary":   { "max_attempts": 5, "base_delay_ms": 10000, "max_delay_ms": 60000, "jitter": true },
    "secondary": { "max_attempts": 2, "base_delay_ms": 300,   "max_delay_ms": 3000,  "jitter": true }
  },
  "confidence_score": {
    "enabled": true,
    "min_threshold": 70,
    "action_below_threshold": "pass"
  }
}
```

- `fallback_enabled` — bascule sur `secondary_model_key` après épuisement des
  retries du primaire.
- `retry.*` — exponential backoff borné par `max_delay_ms`, jitter optionnel.
- `confidence_score.action_below_threshold` — `"pass"` (skip immédiat) ou
  `"retry"` (un nouvel appel LLM pour le bloc, puis skip si toujours bas).

### `config/llm_rate_limit.json`

```json
{ "enabled": true, "min_interval_ms": 10000 }
```

Throttle simple sur l'ensemble du process : intervalle minimum entre deux
appels LLM, partagé via un verrou.

## Charger la config dans le code

```python
from ocapi.config import settings

api_key = settings.llm.piag_api_key
log_level = settings.logging.level
template_path = settings.paths.permis_template_path
```

Pour les tests, recharger explicitement après `monkeypatch.setenv` :

```python
from ocapi.config import reload_settings

new_settings = reload_settings()
```

## Précédence

Les valeurs sont résolues dans cet ordre (Pydantic Settings) :

1. variables d'environnement du process,
2. fichier `.env` à la racine,
3. valeurs par défaut déclarées dans `ocapi/config.py`.

Les fichiers `config/*.json` sont indépendants : ils ont leurs propres
défauts inline (cf. `_DEFAULT_LLM_*_CONFIG` dans
[`ocapi/llm_utils/config.py`](https://github.com/mte-dgpr/ocapi/blob/main/ocapi/llm_utils/config.py))
appliqués si le fichier est absent ou invalide.
