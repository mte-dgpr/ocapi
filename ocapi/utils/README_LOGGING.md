# Système de Logging OCAPI

Ce document explique comment utiliser le système de logging centralisé d'OCAPI.

## Vue d'ensemble

OCAPI utilise le module standard `logging` de Python avec une configuration centralisée qui permet :
- Logs dans la console et/ou dans un fichier
- Rotation automatique des fichiers de log (par taille et par jour)
- Niveaux de logging configurables (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- Configuration via variables d'environnement
- Options CLI pour contrôler la verbosité

## Configuration

### Variables d'environnement

Ajoutez ces variables dans votre fichier `.env` pour configurer le logging :

```bash
# Niveau de logging (DEBUG, INFO, WARNING, ERROR, CRITICAL)
LOG__LEVEL=INFO

# Fichier de log (laisser vide pour désactiver le logging fichier)
LOG__LOG_FILE=logs/ocapi.log

# Taille maximale d'un fichier de log avant rotation (en octets)
LOG__MAX_BYTES=1048576  # 1024 KB

# Nombre de fichiers de backup à conserver
LOG__BACKUP_COUNT=5

# Activer la rotation quotidienne (true/false)
LOG__USE_TIMED_ROTATION=true

# Afficher les logs dans la console (true/false)
LOG__CONSOLE_OUTPUT=true
```

### Options CLI

Le CLI OCAPI offre deux options pour contrôler le niveau de logging :

```bash
# Mode verbose (niveau DEBUG) - affiche tous les détails
ocapi -v run examples/arretes_html/<AIOT>

# Mode silencieux (niveau WARNING) - affiche uniquement les avertissements et erreurs
ocapi -q run examples/arretes_html/<AIOT>

# Les deux options ne peuvent pas être utilisées ensemble
```

## Utilisation dans le code

### Dans un nouveau module

Pour utiliser le logger dans un nouveau module :

```python
from ocapi.utils.logging_utils import get_logger

_LOGGER = get_logger(__name__)

def ma_fonction():
    _LOGGER.debug("Message de debug détaillé")
    _LOGGER.info("Information générale")
    _LOGGER.warning("Attention, quelque chose d'inhabituel")
    _LOGGER.error("Erreur rencontrée")
    _LOGGER.critical("Erreur critique !")

    # Pour loguer une exception avec sa stacktrace
    try:
        # ... code qui peut lever une exception
        pass
    except Exception as e:
        _LOGGER.exception("Une erreur s'est produite")
```

### Niveaux de logging

Utilisez ces niveaux selon le type d'information :

- **DEBUG** : Informations détaillées pour le debugging (ex: valeurs de variables, étapes détaillées)
- **INFO** : Messages informatifs sur le déroulement normal (ex: "Chargement de 5 fichiers")
- **WARNING** : Avertissements pour des situations inhabituelles mais gérables (ex: "Fichier ignoré")
- **ERROR** : Erreurs qui empêchent une fonctionnalité de s'exécuter
- **CRITICAL** : Erreurs critiques qui peuvent arrêter l'application

### Initialisation du logger (déjà fait)

L'initialisation du logger est automatique dans :
- `ocapi/cli.py` : lors de l'exécution via le CLI
- `ocapi/main.py` : lors de l'exécution directe du main

Vous n'avez **pas besoin** d'initialiser le logger dans vos modules, utilisez simplement `get_logger(__name__)`.

## Format des logs

Les logs suivent ce format détaillé :

```
2026-02-04 14:30:45 - ocapi.cli - INFO - Chargement des arrêtés depuis: examples/arretes_html/<AIOT>
2026-02-04 14:30:45 - ocapi.step_chunking - DEBUG - Processing document 1/10
2026-02-04 14:30:46 - ocapi.step_detection - WARNING - Opération ignorée: format invalide
```

Format : `{timestamp} - {module} - {niveau} - {message}`

## Rotation des fichiers de log

Le système gère automatiquement la rotation des logs :

1. **Rotation par taille** : Quand un fichier atteint `LOG__MAX_BYTES` (défaut: 1024 KB), il est renommé et un nouveau fichier est créé
2. **Rotation quotidienne** : À minuit, un nouveau fichier est créé (si `LOG__USE_TIMED_ROTATION=true`)
3. **Backup** : Les anciens fichiers sont conservés (nombre défini par `LOG__BACKUP_COUNT`)

Exemple de fichiers après rotation :
```
logs/
  ocapi.log           # Fichier courant
  ocapi.log.1         # Backup le plus récent
  ocapi.log.2
  ocapi.log.3
  ocapi.log.4
  ocapi.log.5         # Backup le plus ancien
```

## Exemples d'utilisation

### Exemple 1 : Exécution normale

```bash
# Configuration par défaut (niveau INFO)
ocapi run examples/arretes_html/<AIOT>
```

### Exemple 2 : Debug détaillé

```bash
# Voir tous les détails (niveau DEBUG)
ocapi -v run examples/arretes_html/<AIOT>

# Ou via variable d'environnement
LOG__LEVEL=DEBUG ocapi run examples/arretes_html/<AIOT>
```

### Exemple 3 : Mode silencieux

```bash
# Voir uniquement les warnings et erreurs
ocapi -q run examples/arretes_html/<AIOT>
```

### Exemple 4 : Logs dans un fichier

```bash
# Configurer via variable d'environnement
LOG__LOG_FILE=logs/ocapi.log ocapi run examples/arretes_html/<AIOT>

# Le fichier de log sera créé automatiquement avec rotation
```

## Migration depuis print()

Tous les `print()` du projet ont été migrés vers le logger. Si vous ajoutez du nouveau code :

❌ **Ne pas faire** :
```python
print("Message")
print(f"Erreur: {e}", file=sys.stderr)
```

✅ **À faire** :
```python
_LOGGER.info("Message")
_LOGGER.error(f"Erreur: {e}")
```

## Tests

Pour les tests, vous pouvez capturer les logs ou les désactiver :

```python
import logging

def test_ma_fonction(caplog):
    # Les logs seront capturés par pytest
    with caplog.at_level(logging.INFO):
        ma_fonction()
        assert "Message attendu" in caplog.text

def test_sans_logs():
    # Désactiver temporairement les logs
    logging.disable(logging.CRITICAL)
    ma_fonction()
    logging.disable(logging.NOTSET)
```

## Dépannage

### Les logs n'apparaissent pas dans le fichier

Vérifiez que :
1. `LOG__LOG_FILE` est bien défini
2. Le répertoire parent existe ou peut être créé
3. Vous avez les permissions d'écriture

### Trop de logs

Augmentez le niveau de logging :
```bash
LOG__LEVEL=WARNING  # Afficher uniquement warnings et erreurs
```

### Pas assez de détails

Passez en mode debug :
```bash
ocapi -v run examples/arretes_html/<AIOT>
```

## Bonnes pratiques

1. **Utilisez le bon niveau** : DEBUG pour les détails, INFO pour le déroulement normal, WARNING pour les anomalies
2. **Messages clairs** : Incluez le contexte (fichiers, IDs, valeurs importantes)
3. **Pas de données sensibles** : Ne loguez pas de clés API, mots de passe, etc.
4. **Exception logging** : Utilisez `_LOGGER.exception()` dans les blocs except pour capturer la stacktrace
5. **Performance** : Les logs DEBUG ne sont pas évalués si le niveau est plus élevé, mais évitez les opérations coûteuses dans les arguments

## Ressources

- [Documentation Python logging](https://docs.python.org/3/library/logging.html)
- [Logging HOWTO](https://docs.python.org/3/howto/logging.html)
- Code source : `ocapi/utils/logging_utils.py`
- Configuration : `ocapi/config.py` (classe `LoggingConfig`)
