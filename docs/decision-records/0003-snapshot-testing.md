# ADR 0003 — Snapshot testing

- **Statut** : accepté
- **Date** : TODO

## Contexte

> TODO : nécessité de détecter les régressions sur de vrais cas ICPE, sans dépendre d'un LLM en CI.

## Décision

Mise en place de tests de non-régression "snapshot" qui s'exécutent **sans LLM** (opérations pré-chargées + mock) et comparent le `history.json` et le permis HTML générés à un état attendu versionné dans `snapshots/`.

## Alternatives envisagées

> TODO :
>
> - Tests unitaires uniquement
> - Tests d'intégration avec LLM réel en CI

## Conséquences

> TODO :
>
> - Détection rapide des régressions sur vrais cas
> - Coût de maintenance des snapshots (procédure `ocapi update-snapshots`)
> - Tests snapshot exécutés en PR seulement (cf. `.github/workflows/ci.yml`)
> - Lien avec la publication GitHub Pages des snapshots
