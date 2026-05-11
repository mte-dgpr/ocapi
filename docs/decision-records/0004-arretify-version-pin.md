# ADR 0004 — Pinning de la version Arrêtify

- **Statut** : accepté
- **Date** : 2026

## Contexte

OCAPI consomme du HTML produit par
[Arrêtify](https://github.com/mte-dgpr/arretify) : balises `<section>` avec
`data-spec`, `data-number`, `data-title`, `<footer data-spec="appendix">`,
spans sémantiques `data-spec="visa"`, `data-spec="motifs"`, etc. La quasi-
totalité du code OCAPI dépend de cette structure (sélecteurs CSS dans
`utils/arretify_utils.py`, `step_resolution`, `step_rendering`).

Or Arrêtify est un projet jeune dont le format peut changer entre versions
(renommage d'attributs, restructuration de la hiérarchie DOM, nouveaux
`data-spec`…). Une mise à jour silencieuse de la dépendance pourrait casser
OCAPI sans alerte explicite.

## Décision

OCAPI **bloque** strictement le couple `(major, minor)` de la version
d'Arrêtify installée et **vérifie** la version inscrite dans chaque HTML
d'entrée.

Concrètement :

1. Au chargement, [`config.py`](https://github.com/mte-dgpr/ocapi/blob/main/ocapi/config.py)
   lit la version d'`arretify` via `importlib.metadata.version("arretify")`
   et en extrait `SUPPORTED_ARRETIFY_VERSION` = `"<major>.<minor>.X"` (par
   ex. `"0.2.X"`) plus le pattern de regex
   `SUPPORTED_ARRETIFY_VERSION_PATTERN`.

2. Pour chaque arrêté chargé, `validate_arretify_version` (dans `types.py`)
   vérifie que l'attribut `data-arretify_version` du `<body>` matche le
   pattern. Si non, lève `InvalidFileFormatError` avec un message clair :

   ```
   Unsupported Arrêtify version: 0.3.0 (file: 2024-09-27_….html)
   OCAPI supports only versions 0.2.X
   Detected version: 0.3.0
   ```

3. La dépendance dans `pyproject.toml` est figée par compatible release :

   ```toml
   dependencies = [
     "arretify~=0.2.0",
     ...
   ]
   ```

   `~=0.2.0` accepte `0.2.x` mais bloque `0.3.0`.

## Alternatives envisagées

- **Pinning exact (`arretify==0.2.0`)** — trop restrictif, empêche les patchs
  bugfix.
- **`>=0.2`** sans validation HTML — accepte n'importe quelle version
  ultérieure, casserait OCAPI silencieusement à un bump majeur.
- **Adapter dynamiquement à plusieurs versions** — coût d'entretien
  disproportionné par rapport à la fréquence de release d'Arrêtify et au
  périmètre actuel d'OCAPI.

## Conséquences

### Positives

- **Échec rapide et explicite** quand la version diverge, en local comme en
  CI.
- **Snapshots stables** : les fixtures versionnées sont toujours produites
  par la même version d'Arrêtify.
- **Procédure de bump claire** : un humain doit explicitement modifier
  `pyproject.toml` ET valider que les snapshots passent.

### Négatives

- À chaque sortie majeure/mineure d'Arrêtify, il faut une PR OCAPI dédiée
  pour bumper, regénérer les snapshots, valider l'éval détection.
- Si on charge un HTML vieux (généré par une version obsolète d'Arrêtify),
  il faut le re-tagger avant de pouvoir l'utiliser.

### Procédure de bump

1. Bumper `arretify~=X.Y.0` dans `pyproject.toml`.
2. `pip install -e .[dev]`.
3. Régénérer les snapshots : `UPDATE_SNAPSHOTS=1 pytest -m snapshot -v`.
4. Réviser les diffs (souvent purement cosmétiques HTML).
5. Lancer l'éval détection sur quelques modèles pour vérifier qu'aucune
   formulation déterminante n'a régressé.
6. Committer en un seul changement « bump arretify to X.Y ».
