# Décisions d'architecture (ADR)

Cette section archive les décisions structurantes prises au cours du développement d'OCAPI : pourquoi tel choix, quelles alternatives ont été écartées, quelles conséquences. Format léger inspiré des [Architecture Decision Records](https://adr.github.io/) (~1 page : contexte, décision, alternatives, conséquences).

Quand prendre un ADR ?

- Choix de techno ou de bibliothèque non trivial.
- Refonte d'une API publique.
- Décision avec impact transverse (pinning de version, format de fichier, mode d'exécution).
- Compromis qu'on aimerait justifier dans 6 mois.

Quand **ne pas** en prendre :

- Détail d'implémentation interne d'un module.
- Décision réversible sans coût (renommage, refacto local).
- Bug fix.

## Index

- [0001 — Pipeline en étapes explicites](0001-three-step-pipeline.md)
- [0002 — Détection des opérations par LLM](0002-llm-for-detection.md)
- [0003 — Snapshot testing sans LLM](0003-snapshot-testing.md)
- [0004 — Pinning Arrêtify ~=0.2.0](0004-arretify-version-pin.md)
- [0005 — Pydantic Settings + dual config (env + JSON)](0005-pydantic-settings-dual-config.md)

Pour ajouter un ADR : copier le format d'un existant, numéroter à la suite (`000X-<slug>.md`), ajouter au sommaire ci-dessus et à la nav (`mkdocs.yml`).
