# LLM

Tout ce qui concerne l'usage du LLM dans OCAPI : modèles, prompts, résilience, coûts.

## Sommaire

## Modèles supportés

## Sélection du modèle (`config/llm_models.json`)

## Prompts

## Résilience (retry, fallback, timeout)

## Rate limiting

## Mocks et tests sans LLM

## Évaluation et benchmark

## Coûts et latence

> TODO :
>
> - Lister les modèles configurés dans `config/llm_models.json` et leur usage
> - Documenter la stratégie primary / secondary
> - Décrire les prompts (`ocapi/llm_utils/prompts.py`, `ocapi/step_detection/prompts.py`)
> - Expliquer le mock LLM utilisé en snapshot testing
> - Référencer [`scripts/evaluate_detection.py`](https://github.com/mte-dgpr/ocapi/blob/main/scripts/evaluate_detection.py) et la méthodologie d'éval
> - Donner un ordre de grandeur des coûts par AIOT
