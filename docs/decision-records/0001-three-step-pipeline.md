# ADR 0001 — Pipeline en trois étapes

- **Statut** : accepté
- **Date** : TODO

## Contexte

> TODO : décrire le besoin (consolidation d'arrêtés ICPE), pourquoi un découpage en étapes était souhaitable.

## Décision

Le pipeline OCAPI est découpé en trois étapes successives :

1. **Detection** — extraction des opérations depuis les arrêtés.
2. **Resolution** — construction de l'historique consolidé.
3. **Rendering** — génération du permis consolidé HTML.

## Alternatives envisagées

> TODO : pipeline monolithique, découpage plus fin, etc.

## Conséquences

> TODO :
>
> - Avantages (testabilité, possibilité de désactiver une étape, snapshot par étape)
> - Inconvénients (sérialisation/désérialisation entre étapes, duplication potentielle)
> - Impact sur les artefacts intermédiaires (`operations.json`, `history.json`)
