# Logging

OCAPI utilise le module `logging` standard de Python avec une initialisation
centralisée. Configuration via `.env` (préfixe `LOG_`, classe `LoggingConfig`)
ou flags CLI.

## Initialisation

Faite automatiquement par les deux entrées (`ocapi/cli.py` et `ocapi/main.py`)
via [`initialize_root_logger`](https://github.com/mte-dgpr/ocapi/blob/main/ocapi/utils/logging_utils.py).
Dans le code applicatif, **ne pas réinitialiser** : se contenter d'obtenir un
logger nommé.

```python
from ocapi.utils.logging_utils import get_logger

_LOGGER = get_logger(__name__)

def ma_fonction():
    _LOGGER.info("Chargement…")
    try:
        ...
    except Exception:
        _LOGGER.exception("Échec inattendu")
```

`__name__` produit la hiérarchie standard (`ocapi.step_detection.chunking`),
exploitable pour filtrer / silencer un sous-module.

## Configuration

| Variable env | Défaut | Sens |
|---|---|---|
| `LOG_LEVEL` | `INFO` | Niveau global (`DEBUG` / `INFO` / `WARNING` / `ERROR` / `CRITICAL`). |
| `LOG_LOG_FILE` | `None` | Chemin du fichier de log. Vide = pas de fichier. |
| `LOG_MAX_BYTES` | `1048576` (1 Mio) | Taille max avant rotation. |
| `LOG_BACKUP_COUNT` | `5` | Nombre de backups à conserver. |
| `LOG_USE_TIMED_ROTATION` | `true` | Active la rotation quotidienne en plus de la rotation par taille. |
| `LOG_CONSOLE_OUTPUT` | `true` | Affiche aussi dans la console. |

Voir [Configuration](configuration.md#logging-loggingconfig-préfixe-log_)
pour le détail des bornes / validations Pydantic.

## Flags CLI

```bash
# Verbose (DEBUG)
ocapi -v run snapshots/arretes_html/<AIOT>/

# Quiet (WARNING+)
ocapi -q run snapshots/arretes_html/<AIOT>/
```

`-v` et `-q` priment sur `LOG_LEVEL` mais sont mutuellement exclusifs.

## Format des logs

```
2026-02-04 14:30:45 - ocapi.cli - INFO - Chargement des arrêtés depuis: snapshots/arretes_html/0005804239
2026-02-04 14:30:45 - ocapi.step_detection.chunking - DEBUG - Processing document 1/10
2026-02-04 14:30:46 - ocapi.step_detection - WARNING - Operation skipped (AUTRE type)
```

Schéma : `{timestamp} - {logger} - {level} - {message}`.

## Rotation des fichiers

Quand `LOG_LOG_FILE` est défini :

- **Par taille** : à `LOG_MAX_BYTES`, le fichier est renommé en `.1`, un
  nouveau prend le relais.
- **Par jour** (si `LOG_USE_TIMED_ROTATION=true`) : nouveau fichier à minuit
  même si la taille n'est pas atteinte.
- **Backups** : conservation FIFO de `LOG_BACKUP_COUNT` anciens fichiers.

Layout typique après plusieurs rotations :

```
logs/
  ocapi.log
  ocapi.log.1
  ocapi.log.2
  ocapi.log.3
  ocapi.log.4
  ocapi.log.5
```

## Niveaux par module

`get_logger` renvoie un logger Python standard, donc on peut ajuster
ponctuellement :

```python
import logging

logging.getLogger("ocapi.step_detection").setLevel(logging.DEBUG)
logging.getLogger("ocapi.llm_utils").setLevel(logging.WARNING)
```

Utile pour isoler une étape sans inonder la sortie.

## Tests

Capturer avec `caplog` (pytest) :

```python
import logging

def test_something(caplog):
    with caplog.at_level(logging.WARNING):
        ma_fonction()
    assert "skipped" in caplog.text
```

Pour silencer dans un test :

```python
logging.disable(logging.CRITICAL)
try:
    ma_fonction()
finally:
    logging.disable(logging.NOTSET)
```

## Bonnes pratiques

- Utiliser `_LOGGER.exception(...)` dans un `except` plutôt que
  `_LOGGER.error(str(exc))` : la stacktrace sera incluse.
- Ne pas formatter avec `f""` les messages DEBUG potentiellement coûteux à
  produire ; préférer `_LOGGER.debug("op %s on %s", op_id, target_id)`.
- Pas de secrets dans les logs (clés API, payloads contenant des données
  personnelles). `AppConfig.model_dump_safe()` masque les clés API à
  l'export.
- Préfixer les messages d'étape par `STEP n: NAME` (déjà fait dans
  `pipeline.py`) pour faciliter la lecture des logs longs.
