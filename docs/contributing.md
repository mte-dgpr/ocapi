# Contribuer

## Workflow Git

- Branche depuis `main` : `git checkout -b feat/<sujet>` ou `fix/<sujet>`.
- Une branche = une PR ciblée. Évite les PR fourre-tout.
- Rebase sur `main` avant ouverture (`git fetch origin && git rebase origin/main`).
- Pousse, ouvre la PR sur GitHub, attache le contexte (issue, capture d'écran, snapshot diff).
- Demande la revue ; ne ferme pas les threads de revue toi-même (les reviewers les marquent comme résolus).

### Messages de commit

Convention courte du dépôt (cf. `.cursor/rules/commit-messages.mdc`) :

- une ligne unique, **7 mots maximum** ;
- pas de corps, pas de référence d'issue dans le commit (les outils de tracking suffisent) ;
- formulation factuelle : `add retry for piag timeout`, `fix null check in renderer`, `remove unused helper`.

## Standards de code

- **Python 3.12**, type hints obligatoires (mypy strict via `pyproject.toml`).
- **Black** pour le formatage (`line-length = 100`).
- **isort** profil `black`.
- **flake8** + `flake8-bugbear` (`extend-select = ["I", "B"]`).
- **autoflake** retire les imports inutiles.
- Commentaires courts, en anglais, au présent (cf. `.cursor/rules/code-comments.mdc`). Pas de numéros de ticket.
- Pas d'attribution AI / outil dans le code, les commentaires ou les commits.

## Tests

Tous les modules portent leurs tests à côté (`*_test.py`). `pytest` les ramasse via `python_files = ["*_test.py"]`.

```bash
# Tout
pytest

# Module ciblé
pytest ocapi/step_resolution/

# Sans couverture (plus rapide en dev)
pytest --no-cov -q

# Snapshots
pytest -m snapshot
UPDATE_SNAPSHOTS=1 pytest -m snapshot   # régénère
```

Couverture minimale : **80 %** (configurée dans `addopts`).

## Lint et formatage

```bash
black ocapi/
isort ocapi/
flake8 ocapi/      # ou : flake ocapi/
mypy ocapi/
```

Tout en une passe :

```bash
pre-commit run --all-files
```

## Pre-commit

Une fois `pre-commit install` exécuté (cf. [Installation](installation.md)), chaque commit déclenche : `check-merge-conflict`, `end-of-file-fixer`, `trailing-whitespace`, `check-yaml --unsafe`, `check-json`, `licenseheaders`, `black`, `isort`, `autoflake`, `flake8`, `mypy`, `pytest`.

`mypy` et `pytest` allongent le commit (~30–60 s). Ne pas désactiver les hooks (`--no-verify`) sans raison explicite.

## CI

GitHub Actions exécute :

- `lint` : black + isort + flake8 + mypy ;
- `unit-tests` : `pytest` (couverture incluse).

La PR doit être verte avant merge.

## Cycle de revue

- Réponds aux commentaires en poussant un commit additionnel ; ne réécris pas l'historique tant que la PR est en revue.
- N'utilise pas "Resolve conversation" : c'est au reviewer de fermer ses propres threads (cf. `.cursor/rules/pr-review-threads.mdc`).
- Si une remarque demande un changement structurel hors scope, ouvre une issue de suivi plutôt que d'élargir la PR.

## Ajouter une nouvelle étape au pipeline

1. Crée le dossier `ocapi/step_<nom>/` avec un `__init__.py` qui réexporte la fonction publique.
2. Implémente `step_<nom>.py` (signature : entrée → sortie typée explicitement).
3. Ajoute les tests `step_<nom>_test.py` à côté.
4. Branche l'étape dans `ocapi/pipeline.py` (et `ocapi/main.py` / `ocapi/cli.py` si une option est exposée).
5. Documente dans `docs/pipeline-steps/<nom>.md` et mets à jour `mkdocs.yml`.
6. Mets à jour [Architecture](architecture.md) (au moins le diagramme et la table des étapes).

## Ajouter un LLM

Vue d'ensemble de l'architecture LLM : [LLM](llm.md).

### Ajouter un modèle à un provider déjà supporté

Cas le plus courant (nouvelle version d'un modèle OpenAI, Mistral, Anthropic...).

1. Ajoute une entrée dans [`config/llm_models.json`](https://github.com/mte-dgpr/ocapi/blob/main/config/llm_models.json) :
   ```json
   "mon_alias_model_key": {
     "provider": "openai",
     "model_id": "gpt-5.5",
     "reasoning_model": true
   }
   ```
   `provider` doit être l'un des `SUPPORTED_LLM_PROVIDERS` déjà déclarés
   (`ocapi/llm_utils/config.py`). `reasoning_model` et `temperature` restent
   optionnels.
2. Si le modèle doit pouvoir servir de secours en environnement de dev/test
   quand `config/llm_models.json` est absent, ajoute-le aussi à
   `_DEFAULT_LLM_MODELS_CONFIG` dans `ocapi/llm_utils/config.py`.
3. Ajoute une ligne de tarif dans `_COST_PER_1M_TOKENS`
   (`scripts/evaluate_detection.py`), clé = `model_id` (pas la `model_key`),
   valeur = `(coût input $/1M tokens, coût output $/1M tokens)`. **À ne pas
   oublier** : un `model_id` absent de cette table est silencieusement compté
   à coût nul dans `evaluate_detection.py`, ce qui fausse les comparatifs.
4. Si le modèle doit devenir primaire/secondaire par défaut, mets à jour
   `primary_model_key` / `secondary_model_key` dans `config/llm_models.json`.
5. Mets à jour la table des modèles/exemples dans [docs/llm.md](llm.md) si le
   modèle est significatif (nouveau modèle de référence, changement de
   primaire...).

### Ajouter un nouveau provider

Cas où le provider n'existe pas encore (nouvel endpoint API, nouveau format
de réponse).

1. **Configuration des accès** — dans `LLMConfig` (`ocapi/config.py`), ajoute
   `<provider>_api_key: str | None` et `<provider>_api_url: str` (avec une
   URL par défaut), inclus `<provider>_api_key` dans le
   `field_validator("...api_key")` existant et `<provider>_api_url` dans le
   `field_validator("...api_url")`. Ajoute aussi le masquage de la clé dans
   `to_safe_dict` (les lignes `data["llm"]["<provider>_api_key"] = "***MASKED***"`).
2. **Déclaration du provider** — ajoute le nom du provider à
   `SUPPORTED_LLM_PROVIDERS` et une branche dans `_provider_api_config`
   (`ocapi/llm_utils/config.py`) qui renvoie `(settings.llm.<provider>_api_key,
   str(settings.llm.<provider>_api_url))`.
3. **Payload et réponse** — dans `ocapi/llm_utils/core.py` :
   - `_build_payload` : ajoute le provider aux branches concernées (`n`,
     `temperature`/`reasoning_effort`, tout paramètre spécifique) — par
     défaut le payload est OpenAI-compatible (`messages`, `model`), ne
     surcharge que ce qui diffère ;
   - `_extract_content` : ajoute une branche si le format de réponse n'est
     pas `data["choices"][0]["message"]["content"]` (cas Anthropic
     `data["content"][0]["text"]`) ;
   - `_accumulate_usage` : idem si les clés d'usage token diffèrent de
     `prompt_tokens` / `completion_tokens` (cas Anthropic `input_tokens` /
     `output_tokens`) ;
   - `_make_headers` : ajoute une branche si l'authentification n'est pas
     `Authorization: Bearer <clé>` (cas Anthropic `x-api-key` +
     `anthropic-version`).
4. **Modèle(s)** — déclare au moins un modèle du nouveau provider dans
   `config/llm_models.json` (voir section précédente), avec son tarif dans
   `_COST_PER_1M_TOKENS` (`scripts/evaluate_detection.py`).
5. **Variable d'environnement** — documente `LLM__<PROVIDER>_API_URL` (et la
   clé associée) dans la configuration de déploiement si nécessaire (cf.
   [Configuration](configuration.md)).
6. **Documentation** — ajoute une ligne dans la table "Modèles supportés" de
   [docs/llm.md](llm.md) (`docs/llm.md`).
7. **Tests** — ajoute le nouveau provider aux tests paramétrés existants dans
   `ocapi/llm_utils/config_test.py` et `ocapi/llm_utils/core_test.py`
   (payload, extraction de contenu, headers, comptage de tokens).

## Ajouter ou modifier la documentation

- Les sources sont dans `docs/`. La nav est définie dans `mkdocs.yml`.
- Test local :

  ```bash
  pip install -e .[docs]
  mkdocs serve
  ```

- La CI publie automatiquement sur GitHub Pages à chaque push sur `main` touchant `docs/`, `mkdocs.yml` ou `snapshots/`.

## Décisions structurantes : ADR

Si tu prends une décision non triviale (choix de techno, refonte d'API, nouveau format), crée un ADR dans `docs/decision-records/` numéroté à la suite (`000X-<slug>.md`). Format : contexte, décision, alternatives, conséquences. Exemples : [0001](decision-records/0001-three-step-pipeline.md), [0004](decision-records/0004-arretify-version-pin.md).
