# Étape 1 — Detection

Découpage des arrêtés et détection des opérations (ADD / REPLACE / REMOVE) via LLM.

## Sommaire

## Vue d'ensemble

## Entrées et sorties

## Chunking

## Appel LLM et prompt

## Extraction des opérandes

## Filtrage et post-traitement

## Évaluation (ground-truth)

> TODO :
>
> - Schéma mermaid des sous-étapes (chunking → appel LLM → extract operand)
> - Détailler la stratégie de chunking (`ocapi/step_detection/chunking.py`)
> - Lister les types d'opérations détectées et leur format dans `operations.json`
> - Référencer le prompt utilisé et les paramètres LLM
> - Renvoyer vers [LLM](../llm.md) pour la résilience et le choix du modèle
> - Renvoyer vers [Resolution](resolution.md) pour la suite du pipeline
