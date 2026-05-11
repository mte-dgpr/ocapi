# Usage

Ce guide couvre les cas d'utilisation typiques. Pour la liste exhaustive des options voir la [Référence CLI](cli-reference.md).

## Préparer les données d'entrée

OCAPI consomme les arrêtés au **format HTML d'Arrêtify** : un fichier par arrêté, nommé selon la convention :

```
YYYY-MM-DD_<type>_<description>.html
```

Exemples :

```
2009-12-08_ap d'autorisation_initial.html
2014-01-09_ap prescriptions complémentaires_modification rejets.html
2024-09-27_ap prescriptions complémentaires_mise à jour.html
```

`<type>` doit correspondre à un des libellés reconnus (`ap d'autorisation`, `ap prescriptions complémentaires`, `arrêté préfectoral`, etc.). Les types non pertinents (rapports, fiches Seveso, mises en demeure…) sont automatiquement filtrés ; voir `EXCLUDED_FILE_TYPE_PATTERNS` dans `ocapi/utils/io_utils.py`.

Les fichiers d'un même AIOT vont dans un dossier dédié :

```
data/<AIOT>/arretes_html/
├── 2009-12-08_ap d'autorisation_....html
├── 2014-01-09_ap prescriptions complémentaires_....html
└── 2024-09-27_ap prescriptions complémentaires_....html
```

## Lancer le pipeline complet

```bash
ocapi run data/<AIOT>/arretes_html/
```

Ce qui se passe :

1. Charge les arrêtés et déduit l'AIOT depuis le nom du dossier.
2. Lance `step_detection` (LLM) sur chaque arrêté.
3. Lance `step_resolution` pour reconstruire l'historique des articles.
4. Lance `step_rendering` pour générer le permis consolidé.
5. Écrit les sorties (par défaut sous `data/<AIOT>/arretes_consolidation/<AIOT>/`).

Pour forcer un dossier de sortie :

```bash
ocapi run data/<AIOT>/arretes_html/ --output output/<AIOT>/
```

## Filtrer sur certains arrêtés

Limiter le pipeline à quelques arrêtés (par date) :

```bash
ocapi run data/<AIOT>/arretes_html/ --include 2024-09-27 2023-12-04
```

Limiter la **détection** à partir d'une date (les arrêtés antérieurs sont chargés mais leur contenu sert seulement de base au resolution) :

```bash
ocapi run data/<AIOT>/arretes_html/ --start-date 2014-01-09
```

Marquer un arrêté comme principal pour le rendering (titre, header) :

```bash
ocapi run data/<AIOT>/arretes_html/ --principal-id 2009-12-08
```

## Désactiver detection / rendering

Sauter l'étape de rendering (debug detection + resolution uniquement) :

```bash
ocapi run data/<AIOT>/arretes_html/ --no-rendering
```

Sauter la détection en réutilisant des `operations.json` existantes (mode snapshot, **aucun appel LLM**) :

```bash
ocapi run data/<AIOT>/arretes_html/ \
    --operations-from data/<AIOT>/arretes_consolidation/<AIOT>/ \
    --output output/<AIOT>/
```

## Mode snapshot (sans LLM)

Utile en CI ou pour rejouer un cas connu sans coût LLM. Le fichier `operations.json` doit déjà exister (généré une première fois via `ocapi run` ou `ocapi generate-snapshot-fixtures`).

```bash
ocapi run data/<AIOT>/arretes_html/ \
    --operations-from snapshots/arretes_consolidation/<AIOT>/ \
    --output /tmp/<AIOT>/
```

Voir aussi [Snapshot testing](snapshot-testing.md) pour les tests automatisés.

## Lecture des sorties

Le pipeline écrit trois fichiers dans le dossier de sortie :

```
<output_dir>/
├── operations.json     # opérations détectées (entrée du resolution)
├── history.json        # historique des versions par article
└── permis.html         # permis consolidé (omis si --no-rendering)
```

Schémas détaillés : [Format des données](data-formats.md).

## Logs

```bash
ocapi --verbose run data/<AIOT>/arretes_html/      # DEBUG
ocapi --quiet   run data/<AIOT>/arretes_html/      # WARNING+ uniquement
```

Les logs vont à la fois sur stderr et dans le fichier configuré par `LOGGING__LOG_FILE` (cf. [Logging](logging.md)).

## Évaluer la qualité de la détection

Mesurer précision/rappel/F1 face aux opérations annotées manuellement :

```bash
python scripts/evaluate_detection.py --model openai_gpt5mini
python scripts/evaluate_detection.py --model mistral_medium --aiot 0003013459
```

Détails et sortie XLSX : [Évaluation](evaluation.md).

## En cas de problème

- [Dépannage](troubleshooting.md) — erreurs courantes (LLM, snapshots, rendering).
- [Codes d'erreur](error-codes.md) — signification des `error_codes` dans `operations.json` / `history.json`.
