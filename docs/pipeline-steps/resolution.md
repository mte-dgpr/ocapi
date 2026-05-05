# Étape 2 — Resolution

Construction de l'historique des articles à partir des opérations détectées. **C'est l'étape la plus complexe du pipeline.**

## Sommaire

## Vue d'ensemble

## Entrées et sorties

## Construction du graphe d'opérations

## Tri topologique et détection de cycles

## Application des opérations (`apply_ops`)

## Gestion des conflits

## Format de l'historique (`history.json`)

## Cas limites

> TODO :
>
> - Diagramme mermaid du graphe d'opérations sur un cas type (ADD, REPLACE chaîné, REMOVE)
> - Décrire l'algorithme de `build_op_graph` (`ocapi/step_resolution/build_op_graph.py`)
> - Décrire `apply_ops` et l'ordre d'application
> - Lister les types de conflits et la stratégie adoptée
> - Documenter le format `history.json` (champs, exemples)
> - Lister les cas limites traités et ceux qui ne le sont pas
> - Renvoyer vers [Detection](detection.md) (en amont) et [Rendering](rendering.md) (en aval)
