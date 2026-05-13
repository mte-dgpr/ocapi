# LLM

OCAPI s'appuie sur un LLM pour la **détection des opérations** (étape 2) et,
de manière marginale, pour la résolution des **sous-cibles complexes** (étape 3).
Toute la logique LLM est centralisée dans
[`ocapi/llm_utils/`](https://github.com/mte-dgpr/ocapi/tree/main/ocapi/llm_utils).

## Vue d'ensemble

```mermaid
flowchart LR
  caller[step_detection / apply_ops] --> call[call_llm_api]
  cfg1[config/llm_models.json] --> resolve[config_model_llm]
  resolve --> call
  cfg2[config/llm_resilience.json] --> call
  cfg3[config/llm_rate_limit.json] --> call
  call --> primary["Modèle primaire<br/>retry + jitter"]
  primary -- échec final + fallback --> secondary[Modèle secondaire]
  primary --> resp[Réponse texte]
  secondary --> resp
```

L'entrée publique est `call_llm_api(cfg, prompt)` exporté depuis
[`ocapi/llm_utils/__init__.py`](https://github.com/mte-dgpr/ocapi/blob/main/ocapi/llm_utils/__init__.py).
Les appelants ne connaissent que le prompt et le modèle résolu.

## Modèles supportés

Déclarés dans [`config/llm_models.json`](https://github.com/mte-dgpr/ocapi/blob/main/config/llm_models.json).
Chaque entrée a au minimum `provider` + `model_id` ; `reasoning_model` et
`temperature` sont optionnels.

| Provider | Endpoint env | Spécificités payload |
|---|---|---|
| `mte-piag` | `LLM__PIAG_API_URL` | OpenAI-compatible, `temperature: 0`. |
| `mistral` | `LLM__MISTRAL_API_URL` | OpenAI-compatible, `temperature: 0`. |
| `openai` | `LLM__OPENAI_API_URL` | Si `reasoning_model: true` → `reasoning_effort: high` + `verbosity: low` au lieu de `temperature`. |
| `anthropic` | `LLM__ANTHROPIC_API_URL` | API Messages, `max_tokens: 4096`, header `anthropic-version: 2023-06-01`. |
| `google` | `LLM__GOOGLE_API_URL` | Endpoint Gemini compatible OpenAI. |

### Sélection du modèle

[`config_model_llm(model=None)`](https://github.com/mte-dgpr/ocapi/blob/main/ocapi/llm_utils/config.py)
résout :

- `None` ou `"primary"` → `primary_model_key` ;
- `"secondary"` → `secondary_model_key` (lève `LLMConfigError` si non défini) ;
- une `model_key` du JSON ;
- un `model_id` (résolution inverse parmi les modèles déclarés) ;
- quelques alias historiques (`GPT5`, `GPT5mini`,
  `mte-api-piag-mistral-medium-latest`).

Si le fichier est absent ou invalide, des défauts inline pris en charge dans
`_DEFAULT_LLM_MODELS_CONFIG` s'appliquent (primaire = `piag_mistral_medium`).

## Prompts

Tous les prompts sont en français et regroupés dans
[`ocapi/llm_utils/prompts.py`](https://github.com/mte-dgpr/ocapi/blob/main/ocapi/llm_utils/prompts.py).

- `prompt_detection(html)` — utilisé par chaque bloc dans
  [`step_detection`](pipeline-steps/detection.md). Demande au modèle une **liste
  JSON** d'opérations typées (`ADD` / `REPLACE` / `REMOVE` / `AUTRE`) avec
  `source_article`, `target_arrete`, `target_article`, `sub_target`,
  `new_content_start_marker` / `end_marker` et `confidence_score` (0–100). Les
  formulations courantes en français (« abroger », « modifier et remplacer »…)
  sont décrites explicitement pour réduire les faux positifs.
- `query_llm_for_subtarget(...)` — appelé par
  [`apply_ops`](pipeline-steps/resolution.md#sous-cibles-complexes) sur les
  `sub_target.type == COMPLEX` pour faire localiser la portion à remplacer
  dans l'article cible. Désactivable globalement via le flag `enable_llm` du
  pipeline (transformé en `ErrorCode.DISABLED_LLM_CALL`).
- `parse_llm_json_list_response(raw)` — extrait une liste JSON depuis une
  réponse possiblement entourée de texte / fences markdown ; tolérante aux
  petites malformations.
- `extract_html_from_llm_response(...)` — extrait le HTML retourné par le LLM
  pour la résolution de sous-cibles.

## Résilience

[`config/llm_resilience.json`](https://github.com/mte-dgpr/ocapi/blob/main/config/llm_resilience.json)
pilote retries, fallback, timeout et confidence score :

| Champ | Effet |
|---|---|
| `timeout_seconds` | Timeout HTTP par appel (`requests.post`). |
| `retry.primary` / `retry.secondary` | `max_attempts`, backoff exponentiel borné par `max_delay_ms`, `jitter` aléatoire ±20 %. |
| `fallback_enabled` | Si `true` et `secondary_model_key` défini, bascule sur le secondaire après épuisement du primaire. |
| `confidence_score.enabled` | Active le filtrage par score de confiance des opérations. |
| `confidence_score.min_threshold` | Seuil 0–100 ; en-dessous, l'opération est skip ou re-tentée. |
| `confidence_score.action_below_threshold` | `"pass"` (skip immédiat) ou `"retry"` (un appel LLM supplémentaire pour le bloc, puis skip si toujours bas). |

Les erreurs HTTP retryables sont : timeouts, erreurs de connexion, `429` et
toutes les `5xx`. Quand le serveur renvoie un header `Retry-After`, il prend
le pas sur le délai calculé.

## Rate limiting

[`config/llm_rate_limit.json`](https://github.com/mte-dgpr/ocapi/blob/main/config/llm_rate_limit.json)
applique un **intervalle minimum global** entre deux appels LLM (verrou
`threading.Lock` partagé). Utile pour respecter les quotas d'API très
restrictifs (PIAG en particulier, d'où le défaut `min_interval_ms: 10000` dans
le repo).

## Comptage des tokens

`call_llm_api` accumule l'usage côté process via `TokenUsage`. Récupérer le
total :

```python
from ocapi.llm_utils import get_accumulated_usage, reset_accumulated_usage

reset_accumulated_usage()
# ... appels du pipeline ...
usage = get_accumulated_usage()
print(usage.prompt_tokens, usage.completion_tokens, usage.total_tokens)
```

## Mode sans LLM

Deux leviers complémentaires :

- **Pipeline** : `--operations-from <dir>` (CLI) ou
  `enable_detection=False` + `operations=[...]` (`run_pipeline`) — la détection
  est sautée et les opérations sont chargées depuis `operations.json`.
- **Resolution** : `enable_llm=False` (`run_pipeline` / `step_resolution`) —
  les sous-cibles `COMPLEX` ne déclenchent pas d'appel LLM et héritent
  `ErrorCode.DISABLED_LLM_CALL` au lieu d'être consolidées.

Pour les tests unitaires, des mocks vivent dans
[`ocapi/llm_utils/mocks.py`](https://github.com/mte-dgpr/ocapi/blob/main/ocapi/llm_utils/mocks.py).
Les tests **snapshot** s'exécutent dans ces deux modes combinés (cf.
[ADR 0003](decision-records/0003-snapshot-testing.md)).

## Évaluation

Le script [`scripts/evaluate_detection.py`](https://github.com/mte-dgpr/ocapi/blob/main/scripts/evaluate_detection.py)
mesure précision / rappel / F1 d'un modèle contre un ground-truth annoté
(dossier `examples/ground-truth/`). Une opération est correcte si **source**,
**target** et **operation_type** correspondent exactement.

```bash
python scripts/evaluate_detection.py --model openai_gpt5mini
python scripts/evaluate_detection.py --model mistral_medium --aiot 0003013459
```

Les `model` acceptés sont les `model_key` de `config/llm_models.json`.
