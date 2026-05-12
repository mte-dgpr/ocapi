# OCAPI

**OCAPI** (Outil de Consolidation Automatique des Permis ICPE) est un pipeline qui génère un permis ICPE consolidé à partir des arrêtés préfectoraux successifs d'un site classé.

À partir d'un dossier d'arrêtés HTML — un arrêté d'autorisation initial puis ses arrêtés complémentaires —, OCAPI :

1. **annote** le HTML Arrêtify avec des balises sémantiques d'opérations (verbes, références, sous-cibles) ;
2. **détecte** les opérations (ajout, modification, suppression d'articles) introduites par chaque arrêté ;
3. **résout** ces opérations dans l'ordre chronologique pour reconstruire l'historique de chaque article ;
4. **génère** un permis HTML consolidé reflétant l'état en vigueur des prescriptions.

Le projet vise les inspecteurs et bureaux d'études qui doivent reconstituer la version courante d'un arrêté préfectoral sans suivre manuellement la chaîne des modifications.

## Sommaire

- [Architecture](architecture.md) — vue d'ensemble du pipeline
- [Installation](installation.md) — prérequis et mise en place
- [Configuration](configuration.md) — variables d'environnement et fichiers `config/`
- [Usage](usage.md) — cas d'utilisation principaux
- [Référence CLI](cli-reference.md) — toutes les commandes et options
- Étapes du pipeline
    - [Tagging](pipeline-steps/tagging.md)
    - [Detection](pipeline-steps/detection.md)
    - [Resolution](pipeline-steps/resolution.md)
    - [Rendering](pipeline-steps/rendering.md)
- [LLM](llm.md) — modèles, prompts, résilience
- [Format des données](data-formats.md) — schémas d'entrée et de sortie
- [Snapshot testing](snapshot-testing.md) — tests de non-régression
- [Évaluation](evaluation.md) — mesure de la détection vs ground-truth
- [Logging](logging.md)
- [Codes d'erreur](error-codes.md)
- [Décisions d'architecture (ADR)](decision-records/index.md)
- [API](api/index.md)
- [Contribuer](contributing.md)
- [Dépannage](troubleshooting.md)
- [Roadmap](roadmap.md)
- [Glossaire](glossary.md)
