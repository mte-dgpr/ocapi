# ADR 0001 — Pipeline en étapes explicites

- **Statut** : accepté
- **Date** : 2026-01

## Contexte

OCAPI doit produire un permis ICPE consolidé à partir d'une série d'arrêtés préfectoraux hétérogènes (AP d'autorisation + APC). Le traitement combine plusieurs préoccupations très différentes :

- analyse en langage naturel (interpréter des phrases comme "à l'article 5.2, le 3ᵉ alinéa est supprimé") ;
- mécanique de graphe (chaîner les opérations dans le bon ordre, propager les erreurs) ;
- génération HTML lisible.

Mélanger ces préoccupations dans une seule fonction rendrait l'outil difficile à tester, à itérer et à déboguer (un échec LLM masquerait un bug de rendering, etc.).

## Décision

Le pipeline est découpé en étapes successives, exposées comme fonctions Python indépendantes et orchestrées par `ocapi/pipeline.py:run_pipeline` :

1. **Tagging** (`step_tagging`) — annotation sémantique du HTML Arrêtify.
2. **Detection** (`step_detection`) — extraction d'opérations brutes, principalement via LLM.
3. **Resolution** (`step_resolution`) — graphe d'opérations + reconstruction des historiques.
4. **Rendering** (`step_rendering`) — génération du permis HTML.

Chaque étape a un type d'entrée et de sortie clair (`ArreteFile`, `Operation`, `ArticleHistory`, `Permis`). Chacune peut être désactivée indépendamment (`enable_detection`, `enable_rendering`, `enable_tagging`).

## Alternatives envisagées

- **Pipeline monolithique** : une seule fonction qui lit les HTML et écrit le permis. Rejeté : impossible à tester par morceau et à rejouer (mode snapshot).
- **Découpage plus fin** (chunking, validation, persistance comme étapes séparées) : rejeté pour le moment ; les sous-modules existent (`chunking.py`, `extract_operand.py`, etc.) mais restent rangés sous l'étape qui les consomme. Quatre étapes restent un compromis lisible.
- **Orchestrateur externe** (Airflow, Prefect, Dagster) : disproportionné pour un traitement qui s'exécute séquentiellement sur un AIOT.

## Conséquences

Positives :

- Mode snapshot trivial : on saute la détection (`--operations-from`) et on charge des `operations.json` existantes.
- Tests unitaires par étape (couverture par module).
- Évolution indépendante : on peut remplacer la détection LLM par une approche basée tags (`step_tagging`) sans toucher au resolution.

Négatives :

- Légère redondance dans les structures intermédiaires (`RawOperation` → `Operation`, `ArreteFile` partagé entre étapes).
- Chaque étape doit documenter explicitement ses contrats d'entrée/sortie ; la dérive est facile sans ces docs.
