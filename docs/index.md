# OCAPI

**OCAPI** (Outil de Consolidation Automatique des Permis ICPE) est un pipeline de traitement automatisé des arrêtés préfectoraux pour les installations classées pour la protection de l'environnement (ICPE).

## Sommaire

- [Architecture](architecture.md) — vue d'ensemble du pipeline
- [Installation](installation.md) — prérequis et mise en place
- [Configuration](configuration.md) — variables d'environnement et fichiers `config/`
- [Usage](usage.md) — cas d'utilisation principaux
- [Référence CLI](cli-reference.md) — toutes les commandes et options
- Étapes du pipeline
    - [Detection](pipeline-steps/detection.md)
    - [Resolution](pipeline-steps/resolution.md)
    - [Rendering](pipeline-steps/rendering.md)
- [LLM](llm.md) — modèles, prompts, résilience
- [Décisions d'architecture (ADR)](decision-records/index.md)
- [API](api/index.md)
- [Contribuer](contributing.md)
- [Dépannage](troubleshooting.md)
- [Glossaire](glossary.md)

> TODO :
>
> - Pitch en 2-3 phrases du projet et de son public cible
> - Statut du projet (alpha, périmètre couvert, limites connues)
> - Liens vers les exemples publiés sur GitHub Pages (`/snapshots/`)
> - Un schéma "vue d'ensemble" (mermaid) du flux global
