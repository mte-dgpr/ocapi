# ADR 0003 — Snapshot testing sans LLM

- **Statut** : accepté
- **Date** : 2026-02

## Contexte

Le pipeline OCAPI est sensible à des changements peu visibles : modification d'un prompt, refactor du resolution, ajout d'un cas de filtrage… Il faut détecter rapidement les régressions sur de **vrais** cas ICPE, sinon on découvre les écarts en production.

Trois contraintes :

1. La CI ne doit pas dépendre du réseau PIAG ni payer d'appels LLM à chaque PR.
2. Les cas de référence doivent rester compréhensibles (vrais arrêtés HTML) et versionnés.
3. La régénération des références doit être triviale après une modification volontaire.

## Décision

Mettre en place un test pytest paramétré sur des cas réels (`pytest -m snapshot`) :

- Les cas vivent dans `snapshots/arretes_html/<AIOT>/` (HTML d'entrée) et `snapshots/arretes_consolidation/<AIOT>/` (sortie attendue : `operations.json`, `history.json`, `permis.html`).
- Le test exécute le pipeline en `enable_detection=False, enable_llm=False`, en chargeant les `operations.json` versionnées plutôt qu'en appelant un LLM.
- Les sorties sont comparées exactement aux fichiers attendus (`operations.json`, `history.json`, normalisation HTML pour `permis.html`).
- `UPDATE_SNAPSHOTS=1 pytest -m snapshot` (ou `ocapi update-snapshots`) régénère les fichiers attendus.

Détails d'implémentation et workflow : [Snapshot testing](../snapshot-testing.md).

## Alternatives envisagées

- **Tests unitaires uniquement** : insuffisants pour détecter les régressions cross-module (chaînage detection → resolution → rendering).
- **Tests d'intégration avec LLM réel en CI** : trop lent, coûteux, dépendant du réseau PIAG, et instables (réponses LLM non déterministes).
- **Snapshot par enregistrement / replay des appels HTTP** : plus complexe à entretenir que de versionner directement les `operations.json` produits.
- **Diff sémantique** des `history.json` (ignorer l'ordre des champs) : abandonné pour rester sur une comparaison exacte ; on reformat avec `strip_none_values` et tri stable des `error_codes` au moment de la sérialisation pour éviter le faux positif.

## Conséquences

Positives :

- CI rapide et hors-ligne (pas d'appel LLM).
- Diff Git lisible quand la sortie change (les fichiers attendus sont versionnés).
- Évaluation chirurgicale d'un changement (regarder le diff de `permis.html` ou `history.json`).

Négatives :

- Les snapshots dérivent : régénération nécessaire à chaque évolution du resolution / rendering. C'est attendu mais demande de bien relire le diff avant de commiter.
- Ne couvre pas la qualité de la détection LLM : c'est `scripts/evaluate_detection.py` qui s'en charge ([Évaluation](../evaluation.md)).
- Dépendance forte à la version d'Arrêtify : un bump invalide les snapshots ([ADR 0004](0004-arretify-version-pin.md)).
