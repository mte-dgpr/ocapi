# ADR 0002 — Détection des opérations par LLM

- **Statut** : accepté
- **Date** : 2026-01

## Contexte

Détecter les opérations introduites par un APC revient à interpréter du langage administratif libre :

> "À l'article 5.2.1 de l'arrêté préfectoral d'autorisation susvisé, le 3ᵉ alinéa est remplacé par : « … »."
> "L'article 7 est abrogé."
> "Il est ajouté à l'article 4.3 le tableau suivant : …"

Ces phrases varient en formulation, en ordre et en granularité d'une décennie / d'un préfet à l'autre. Les éléments à extraire sont :

- le **type** d'opération (ADD / REPLACE / REMOVE) ;
- l'**arrêté cible** (souvent désigné par sa date) ;
- l'**article cible** (référence numérique avec sous-niveaux) ;
- la **sub-target** éventuelle (alinéa, phrase, ligne de tableau) ;
- l'**operand** (le nouveau contenu, en HTML).

Une approche purement règles a été tentée mais bute sur la diversité des formulations et la richesse du contexte (références implicites à "l'arrêté susvisé", énumérations multi-articles, etc.).

## Décision

L'étape `step_detection` s'appuie sur un appel LLM par chunk d'arrêté. Le prompt est piloté par `ocapi/llm_utils/prompts.py` et la sélection de modèle vient de `config/llm_models.json` (voir [LLM](../llm.md)).

- Modèle primaire et modèle de repli configurables (`primary_model_key`, `secondary_model_key`).
- Résilience centralisée dans `config/llm_resilience.json` (timeout, retry, fallback automatique).
- Rate limiting optionnel via `config/llm_rate_limit.json`.
- Mode snapshot (`enable_llm=False`, `--operations-from`) pour rejouer un cas sans coût LLM.

Une couche de tagging Arrêtify (`step_tagging`) prépare le HTML pour faciliter la validation et, à terme, fournir une voie de détection structurée alternative ([ADR à venir](index.md)).

## Alternatives envisagées

- **Règles / heuristiques pures** : trop fragile face aux formulations atypiques. Conservé en filet pour les patterns simples (cf. `step_tagging/operations_detection.py`).
- **Modèle NER spécialisé** entraîné sur des arrêtés annotés : pas assez de données annotées pour démarrer ; coût d'annotation élevé. Reste une piste long-terme (cf. [Roadmap](../roadmap.md)).
- **Approche hybride règles + LLM** : c'est ce qu'on fait dans la pratique (le tagging extrait les références sûres, le LLM gère le reste).
- **Modèle local** (open-weights) : évalué pour réduire la dépendance PIAG, pas encore au niveau pour la détection complète.

## Conséquences

Positives :

- Robustesse face à la variété des formulations.
- Itérations rapides : changer un prompt ne demande pas de réentraîner un modèle.
- Évaluation chiffrée possible (`scripts/evaluate_detection.py` mesure précision / rappel / F1 vs ground-truth).

Négatives :

- Dépendance réseau (PIAG) en exécution, et donc en CI : c'est ce qui a motivé le mode snapshot et l'[ADR 0003](0003-snapshot-testing.md).
- Coût par appel non négligeable sur des AIOT volumineux.
- Variabilité (même prompt, deux résultats légèrement différents) : on l'absorbe via les snapshots et l'évaluation périodique sur le ground-truth.
