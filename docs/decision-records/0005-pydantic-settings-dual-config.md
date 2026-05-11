# ADR 0005 — Pydantic Settings + double config

- **Statut** : accepté
- **Date** : 2026

## Contexte

OCAPI a deux familles très différentes de paramètres :

1. **Variables d'environnement / secrets** — clés API LLM, chemins absolus,
   préférences de logging. Spécifiques à chaque déploiement, contiennent des
   secrets, ne doivent **pas** être versionnées.
2. **Réglages comportementaux du LLM** — modèle primaire/secondaire, retries,
   timeouts, rate-limit, seuil de confidence score. Communs à toute l'équipe,
   doivent être **versionnés** pour reproductibilité et review.

Mélanger les deux dans une seule mécanique introduisait soit :

- des secrets dans le repo,
- soit une explosion de variables d'environnement pour des paramètres qui
  n'ont aucune raison d'être par-déploiement (ex. `RETRY_MAX_ATTEMPTS_PRIMARY`).

## Décision

OCAPI utilise **deux mécaniques distinctes** :

### `.env` + Pydantic Settings (`ocapi/config.py`)

Pour tout ce qui dépend du déploiement / contient des secrets :

- clés et URLs des fournisseurs LLM (`LLM__PIAG_API_KEY`, …),
- chemins de fichiers (`PATHS__PROJECT_ROOT`, `PATHS__PERMIS_TEMPLATE_PATH`),
- logging (`LOG_LEVEL`, `LOG_LOG_FILE`, …).

Pydantic Settings apporte :

- typage strict et validation au démarrage (regex URLs, bornes numériques,
  `Path.exists()`),
- chargement transparent depuis `.env`,
- support du préfixe et du séparateur imbriqué (`env_nested_delimiter="__"`)
  pour structurer (`LLM__PIAG_API_KEY` → `settings.llm.piag_api_key`),
- masquage des secrets via `model_dump_safe()`.

### Fichiers JSON sous `config/` (`ocapi/llm_utils/config.py`)

Pour les réglages comportementaux versionnés :

- `config/llm_models.json` — déclaration des modèles, choix
  primaire/secondaire,
- `config/llm_resilience.json` — retries, timeout, fallback,
  confidence_score,
- `config/llm_rate_limit.json` — throttle global.

Avantages :

- **Reviewables en PR** : un changement de modèle ou de seuil est explicite
  dans le diff.
- **Indépendants du déploiement** : la même CI tourne avec les mêmes
  réglages que la production.
- **Tolérants** : si le fichier est absent ou invalide, des défauts inline
  (`_DEFAULT_*_CONFIG`) prennent le relais avec un warning.

## Alternatives envisagées

- **Tout dans `.env`** — pollution de l'environnement, secrets et réglages
  équipe se mélangent, perte de la review.
- **Tout dans des YAML/JSON versionnés** — obligerait à versionner les clés
  API ou à inventer un mécanisme de templating type `!env`. Sortie du
  périmètre Pydantic Settings.
- **Un seul fichier (TOML, YAML)** avec sections — possible mais Pydantic
  Settings reste cantonné à `.env` / env vars dans la pratique courante ; le
  mélange n'aurait pas simplifié.
- **Bibliothèque type Dynaconf / Hydra** — surenginée pour le périmètre
  actuel.

## Conséquences

### Positives

- Frontière claire entre « ce qui change par déploiement » et « ce qui est
  un choix d'équipe ».
- Possibilité de modifier les réglages LLM en CI via un PR sans toucher au
  déploiement.
- `.env.example` reste léger (clés API + chemins, c'est tout).

### Négatives

- **Deux endroits à connaître** pour configurer OCAPI. La page
  [Configuration](../configuration.md) doit toujours documenter les deux.
- Risque de confusion : tentation de mettre un secret dans `config/llm_models.json`
  ou un réglage d'équipe dans `.env`. Discipline à entretenir en review.
- Les défauts inline dans `_DEFAULT_LLM_*_CONFIG` peuvent diverger des
  fichiers JSON si on les édite sans mettre à jour les défauts. Le warning
  remonté en cas de fichier manquant rend la divergence visible.

### Procédure de modification

- **Changer de modèle LLM par défaut** → PR sur `config/llm_models.json`
  (revue + éval éventuelle).
- **Augmenter le timeout en production** → variable d'env `…` non, c'est un
  réglage équipe : PR sur `config/llm_resilience.json`.
- **Ajouter un nouveau provider** → variables `LLM__<NEW>_API_KEY` /
  `LLM__<NEW>_API_URL` dans `LLMConfig`, `_provider_api_config` dans
  `llm_utils/config.py`, et déclaration du modèle dans `config/llm_models.json`.
