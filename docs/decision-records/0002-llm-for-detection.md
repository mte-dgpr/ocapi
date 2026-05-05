# ADR 0002 — Détection par LLM

- **Statut** : accepté
- **Date** : TODO

## Contexte

> TODO : décrire la difficulté d'extraire des opérations (ADD / REPLACE / REMOVE) à partir d'arrêtés HTML hétérogènes, et pourquoi les approches purement règles n'étaient pas suffisantes.

## Décision

L'étape de détection s'appuie sur un LLM via un prompt dédié, configurable via `config/llm_models.json`.

## Alternatives envisagées

> TODO :
>
> - Règles / heuristiques pures
> - Modèles spécialisés NER
> - Approches hybrides

## Conséquences

> TODO :
>
> - Dépendance à une API LLM (PIAG, OpenAI, Mistral, ...)
> - Coût et latence
> - Stratégie de résilience (retry, fallback, mocks)
> - Besoin d'une boucle d'évaluation (`scripts/evaluate_detection.py`)
