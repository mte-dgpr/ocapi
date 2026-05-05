# Architecture

Vue d'ensemble du pipeline OCAPI, de ses composants et de leurs interactions.

## Sommaire

## Vue d'ensemble

## Pipeline en trois étapes

## Modèle de données

## Dépendances externes (Arrêtify, LLM, ...)

## Flux des données

## Décisions d'architecture associées

- [ADR 0001 — Pipeline en trois étapes](decision-records/0001-three-step-pipeline.md)
- [ADR 0002 — Détection par LLM](decision-records/0002-llm-for-detection.md)
- [ADR 0003 — Snapshot testing](decision-records/0003-snapshot-testing.md)

> TODO :
>
> - Diagramme mermaid du pipeline complet (entrées, étapes, sorties)
> - Description du modèle de données (`ocapi/types.py`)
> - Détailler les frontières avec Arrêtify
> - Lister les artefacts produits par étape (operations.json, history.json, permis_consolidé.html)
> - Préciser les invariants entre étapes
