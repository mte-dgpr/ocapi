# Glossaire

Termes métier (ICPE) et vocabulaire propre à OCAPI.

## Termes ICPE

### AIOT

Activité, Installation, Ouvrage ou Travaux. Identifiant national d'un site industriel classé ICPE (typiquement un nombre à 10 chiffres). Sert de clé pour regrouper les arrêtés d'un même site.

### Arrêté préfectoral (AP)

Acte administratif pris par le préfet imposant des prescriptions à un AIOT. Tous les arrêtés consommés par OCAPI sont des arrêtés préfectoraux.

### AP d'autorisation

Arrêté qui autorise l'exploitation initiale d'un site et fixe le socle de prescriptions. C'est généralement le plus ancien arrêté de la chaîne ; il sert de base au permis consolidé.

### AP de prescriptions complémentaires (APC)

Arrêté qui modifie un arrêté antérieur (le plus souvent l'AP d'autorisation) en ajoutant, modifiant ou supprimant des articles.

### Article (d'un arrêté)

Unité numérotée d'un arrêté (ex. `Article 5.2`). C'est l'objet que le pipeline tracke version par version dans `history.json`.

### Permis consolidé

Vue à jour des prescriptions applicables, reconstruite en appliquant chronologiquement toutes les opérations détectées sur la base initiale. C'est la sortie principale d'OCAPI (`permis.html`).

### Prescription

Obligation imposée à l'exploitant par un arrêté (mesures techniques, valeurs limites, suivi, etc.). Le permis consolidé regroupe toutes les prescriptions actives.

### Sub-target

Partie ciblée à l'intérieur d'un article (ex. "le 3ᵉ alinéa", "la phrase « … »", "la ligne 7 du tableau"). Décrite par un `SubTarget` typé : `FULL_SECTION`, `PHRASE`, `TABLEAU`, `COMPLEX`.

## Termes OCAPI

### Operation (ADD / REPLACE / REMOVE)

Opération atomique extraite par la détection : insertion d'un article (`ADD`), remplacement d'un contenu (`REPLACE`), suppression (`REMOVE`). Plus une variante `AUTRE` côté `RawOperationType` pour les détections ambiguës.

### RawOperation

Opération telle que détectée par le LLM, avant validation et conversion. Unité de sortie de `step_detection`. Mappée vers `Operation` (typée + références résolues) en entrée du resolution.

### Source / Target

`source` = arrêté qui décrit l'opération (typiquement l'APC le plus récent). `target` = arrêté + article modifié par l'opération (typiquement un arrêté plus ancien). Les deux sont représentés par un `NodeId(arrete_id, article_id)`.

### History

Historique des versions d'un article cible : liste ordonnée de `ArticleVersion` (numéro de version, contenu, opération source, error_codes éventuels). Stocké dans `history.json` ; format détaillé dans [Format des données](data-formats.md).

### NodeId

Couple `(arrete_id, article_id)` qui identifie de manière unique un nœud du graphe d'opérations. Sérialisé `"<arrete_id>#<article_id>"` dans `history.json`.

### NEW_ARTICLE

Préfixe spécial pour `article_id` (`NEW_ARTICLE:5.1`) marquant qu'une opération `ADD` crée un nouvel article qui n'existait pas dans la base.

### Operation graph

`networkx.MultiDiGraph` construit par `step_resolution` : un nœud par couple `(arrete, article)`, une arête par opération source → target. La résolution applique les opérations dans l'ordre chronologique des arrêtés source.

### Chunking

Découpage d'un arrêté HTML en morceaux digestes pour le LLM. Implémenté par `ocapi/step_detection/chunking.py`, conserve la hiérarchie de sections.

### Tagging

Étape qui annote le HTML Arrêtify avec des balises sémantiques (références d'articles, opérations textuelles). Sert de base au resolution avancé. Voir [Tagging](pipeline-steps/tagging.md).

### Snapshot

Cas de référence (arrêtés + opérations + permis attendus) versionné dans `snapshots/arretes_consolidation/<AIOT>/`. Sert aux tests de non-régression sans LLM. Voir [Snapshot testing](snapshot-testing.md).

### Ground-truth

Opérations annotées manuellement par un expert ICPE, conservées dans `examples/ground-truth/`. Sert d'étalon à `scripts/evaluate_detection.py` pour mesurer précision/rappel/F1 du LLM.

### Error code

Drapeau attaché à une opération ou à une version d'article quand quelque chose s'est mal passé (extraction, propagation, sub-target introuvable…). Énuméré dans `ErrorCode` (`ocapi/types.py`). Liste : [Codes d'erreur](error-codes.md).

### Principal

Arrêté marqué comme racine logique du permis consolidé (titre, en-tête). Marqué via `--principal-id` ou via le champ `principal` sur `ArreteFile`.

### Mode snapshot (`enable_llm=False`)

Mode d'exécution sans aucun appel LLM : la détection est remplacée par un chargement d'`operations.json`, et la consolidation des sub-targets complexes est désactivée (les opérations concernées reçoivent `DISABLED_LLM_CALL`).

## Voir aussi

- [Architecture](architecture.md) — vue d'ensemble du flux.
- [Format des données](data-formats.md) — schémas exacts d'`operations.json` et `history.json`.
- [Codes d'erreur](error-codes.md) — sémantique de chaque flag.
