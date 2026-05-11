# Référence CLI

Référence exhaustive des commandes installées par le package `ocapi`. Pour les cas d'usage voir [Usage](usage.md).

## `ocapi`

CLI principal exposé par `ocapi/cli.py` (entry point `ocapi`).

### Options globales

| Option        | Description                                                  |
| ------------- | ------------------------------------------------------------ |
| `--version`   | Affiche la version (`%(prog)s 0.1.0`).                       |
| `-v`, `--verbose` | Force le niveau de log à `DEBUG`.                        |
| `-q`, `--quiet`   | Force le niveau de log à `WARNING`.                      |
| `--help`      | Aide générale ou aide d'une sous-commande (`ocapi run --help`). |

Le niveau de log par défaut vient de `LOGGING__LEVEL` ([Configuration](configuration.md)).

### `ocapi run`

Charge les arrêtés HTML et exécute le pipeline (tagging → detection → resolution → rendering).

```text
ocapi run <input_dir> [--aiot AIOT] [--include ID ...] [--start-date YYYY-MM-DD]
                      [--output DIR] [--no-rendering] [--operations-from DIR]
                      [--principal-id YYYY-MM-DD]
```

| Argument / option         | Type   | Description                                                                                          |
| ------------------------- | ------ | ---------------------------------------------------------------------------------------------------- |
| `input_dir`               | Path   | Dossier contenant les arrêtés HTML.                                                                  |
| `--aiot AIOT`             | str    | Identifiant AIOT. Par défaut : nom du dossier `input_dir`.                                           |
| `--include ID [ID ...]`   | list   | Restreint le pipeline aux arrêtés dont l'`id` (date `YYYY-MM-DD`) est listé.                          |
| `--start-date YYYY-MM-DD` | str    | Seuls les arrêtés `> start-date` passent par la détection. Les antérieurs servent de base au resolution. |
| `--output DIR`, `-o`      | Path   | Dossier de sortie. Par défaut : `<input_dir>/../arretes_consolidation/<aiot>/`.                      |
| `--no-rendering`          | flag   | Saute la génération du permis HTML (étape 4).                                                        |
| `--operations-from DIR`   | Path   | Charge `DIR/operations.json` au lieu de lancer la détection (mode snapshot, **aucun appel LLM**).     |
| `--principal-id YYYY-MM-DD` | str  | Marque l'arrêté daté `YYYY-MM-DD` comme principal (titre/header du permis).                          |

Sortie par défaut :

```
<output_dir>/
├── operations.json
├── history.json
└── permis.html         # absent si --no-rendering
```

Codes de retour : voir [Codes de sortie](#codes-de-sortie).

### `ocapi update-snapshots`

Régénère les snapshots de référence (sans appeler le LLM ; opérations préchargées + mock).

```bash
ocapi update-snapshots
```

Parcourt `SNAPSHOT_CASES` (`ocapi/snapshot.py`) et écrit `operations.json`, `history.json`, `permis.html` dans `snapshots/arretes_consolidation/<AIOT>/`. Voir [Snapshot testing](snapshot-testing.md).

Équivalent via pytest :

```bash
UPDATE_SNAPSHOTS=1 pytest -m snapshot
```

### `ocapi generate-snapshot-fixtures`

Lance le pipeline complet **avec LLM** sur tous les cas snapshot pour générer les fichiers `operations.json` initiaux.

```bash
ocapi generate-snapshot-fixtures
```

À utiliser une seule fois, ou après une modification volontaire de la détection. Coût LLM réel ; nécessite la configuration PIAG (ou autre fournisseur configuré).

## `python -m ocapi.main`

Variante lourde du même pipeline (`ocapi/main.py`). Conservée pour les scripts existants ; les options reproduisent celles de `ocapi run` (sans le préfixe sous-commande).

```text
python -m ocapi.main <input_dir> [--output DIR] [--aiot AIOT] [--include ID ...]
                                 [--start-date YYYY-MM-DD] [--operations-from DIR]
                                 [--principal-id YYYY-MM-DD] [--no-rendering] [-v|-q]
```

À privilégier `ocapi run` dans la documentation et les nouveaux scripts.

## `flake`

Alias local pour `flake8` ajouté pour raccourcir les commandes pre-commit. Tolère un préfixe `check` (`flake check ocapi/` ≡ `flake8 ocapi/`).

```bash
flake ocapi/
flake check ocapi/
```

Entry point : `ocapi/cli_flake.py:main`.

## Codes de sortie

| Code | Signification                                                          |
| ---- | ---------------------------------------------------------------------- |
| `0`  | Succès.                                                                |
| `1`  | Erreur attendue (`OcapiError`, `InputOutputError`, filtre `--include` vide, etc.). |
| `1`  | Exception inattendue (loggée avec `_LOGGER.exception`).                |

`ocapi --help` (sans sous-commande) retourne `0`.

## Variables d'environnement utilisées

Le CLI lit le `Settings` global (`ocapi/config.py`). Les principales :

- `LLM__PIAG_API_KEY`, `LLM__PIAG_API_URL` — accès LLM.
- `LOGGING__LEVEL`, `LOGGING__LOG_FILE`, `LOGGING__CONSOLE_OUTPUT`, `LOGGING__MAX_BYTES`, `LOGGING__BACKUP_COUNT`, `LOGGING__USE_TIMED_ROTATION` — logs.
- `PIPELINE__FULL_SECTION` — placeholder utilisé par le rendering.
- `PATHS__PROJECT_ROOT`, `PATHS__CATALOGUE_PATH` — chemins absolus utilisés par certains scripts.

Détails et valeurs par défaut : [Configuration](configuration.md).
