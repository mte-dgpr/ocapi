# OCAPI

**OCAPI** (Outil de Consolidation Automatique des Permis ICPE) est un pipeline de traitement automatisé des arrêtés préfectoraux pour les installations classées pour la protection de l'environnement (ICPE).

## 🎯 Objectif

OCAPI permet de :
- **Détecter** automatiquement les opérations (ajout, modification, suppression) dans les arrêtés
- **Résoudre** les conflits et construire l'historique des articles
- **Générer** un permis consolidé en HTML regroupant toutes les prescriptions applicables

## 🏗️ Architecture du pipeline

Le pipeline OCAPI se décompose en 4 étapes principales :

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   STEP 1     │────▶│   STEP 2     │────▶│   STEP 3     │────▶│   STEP 4     │
│   Chunking   │     │  Detection   │     │  Resolution  │     │  Rendering   │
└──────────────┘     └──────────────┘     └──────────────┘     └──────────────┘
   HTML → Docs         Docs → Ops         Ops → History      History → Permis
```

1. **Chunking** : Découpe les fichiers HTML en documents structurés
2. **Detection** : Détecte les opérations via LLM (ajout, modification, suppression)
3. **Resolution** : Résout les conflits et construit l'historique des versions
4. **Rendering** : Génère le permis consolidé HTML final

## 📦 Installation

### Prérequis

- Python 3.10+
- pip

### Installation standard

```bash
# Cloner le dépôt
git clone <repository-url>
cd ocapi

# Créer un environnement virtuel
python -m venv venv
source venv/bin/activate   # Windows : venv\Scripts\activate

# Installer OCAPI
pip install --upgrade pip
pip install -e .
```

### Installation pour le développement

```bash
# Installer avec les dépendances de développement
pip install -e .[dev]

# Activer les hooks pre-commit
pre-commit install
```

## ⚙️ Configuration

OCAPI utilise **Pydantic Settings** pour une configuration typée et validée.

### 1. Créer le fichier de configuration

```bash
# Copier le template
cp .env.example .env

# Éditer le fichier .env
nano .env  # ou votre éditeur préféré
```

### 2. Variables d'environnement principales

```bash
# API LLM (obligatoire pour la production)
PIAG_API_KEY=votre-clé-api
PIAG_API_URL=https://preprod.api.piag.e2.rie.gouv.fr/v1/chat/completions

# Modèle LLM par défaut
DEFAULT_LLM_MODEL=mte-api-piag-mistral-medium-latest

# Logging (préfixe LOG_)
LOG_LEVEL=INFO
LOG_FILE=logs/ocapi.log
LOG_CONSOLE_OUTPUT=true

# Chemins (préfixe PATH_)
PATH_PROJECT_ROOT=/chemin/vers/le/projet
PATH_CATALOGUE_PATH=/chemin/vers/catalogue_ap.json
```

### 3. Utiliser la configuration dans le code

```python
from ocapi.config import settings

# Accéder aux paramètres
api_key = settings.llm.piag_api_key
model = settings.pipeline.default_llm_model
log_level = settings.logging.level
```

## 🚀 Usage

OCAPI propose deux interfaces principales :

### 1. CLI officiel (`ocapi`)

Interface en ligne de commande installée globalement :

```bash
# Afficher l'aide
ocapi --help
ocapi run --help

# Traiter tous les arrêtés d'un répertoire
ocapi run data/0005804239/arretes_html/

# Avec options
ocapi run data/0005804239/arretes_html/ \
    --aiot 0005804239 \
    --output resultat.json

# Filtrer sur des arrêtés spécifiques
ocapi run data/0005804239/arretes_html/ \
    --include 2024-09-27 2023-12-04

# Mode verbose
ocapi --verbose run data/0005804239/arretes_html/
```

**Options disponibles :**
- `--aiot AIOT` : Identifiant AIOT (défaut : déduit du chemin)
- `--include ID [ID...]` : Filtrer sur des arrêtés spécifiques
- `-o, --output FILE` : Fichier de sortie JSON
- `-v, --verbose` : Mode verbose (DEBUG)
- `-q, --quiet` : Mode silencieux (WARNING+)

### 2. Script main.py (`python -m ocapi.main`)

Point d'entrée direct avec options avancées :

```bash
# Afficher l'aide
python -m ocapi.main --help

# Usage basique
python -m ocapi.main data/0005804239/arretes_html/

# Répertoire de sortie personnalisé
python -m ocapi.main data/0005804239/arretes_html/ \
    --output custom_output/

# Ignorer le premier arrêté (AP initial)
python -m ocapi.main data/0005804239/arretes_html/ --skip-first

# Désactiver le rendering (étapes 1-3 uniquement)
python -m ocapi.main data/0005804239/arretes_html/ --no-rendering

# Combiner plusieurs options
python -m ocapi.main data/0005804239/arretes_html/ \
    --include 2024-09-27 2023-12-04 \
    --skip-first \
    --output output/ \
    --verbose
```

**Options supplémentaires :**
- `--skip-first` : Ignorer le premier arrêté (AP initial)
- `--no-rendering` : Désactiver la génération du permis consolidé

## 📁 Structure du projet

```
ocapi/
├── ocapi/                        # Package principal
│   ├── __init__.py
│   ├── cli.py                    # CLI officiel (ocapi run)
│   ├── main.py                   # Point d'entrée direct
│   ├── pipeline.py               # Pipeline simplifié
│   ├── config.py                 # Configuration Pydantic
│   ├── types.py                  # Types et modèles de données
│   │
│   ├── step_chunking/            # Étape 1 : Chunking
│   │   ├── step_chunking.py
│   │   └── step_chunking_test.py
│   │
│   ├── step_detection/           # Étape 2 : Detection
│   │   ├── step_detection.py
│   │   ├── step_detection_test.py
│   │   ├── extract_operand.py
│   │   ├── subtarget_detection.py
│   │   └── prompts.py
│   │
│   ├── step_resolution/          # Étape 3 : Resolution
│   │   ├── step_resolution.py
│   │   ├── apply_ops.py
│   │   ├── apply_ops_test.py
│   │   ├── build_op_graph.py
│   │   └── build_op_graph_test.py
│   │
│   ├── step_rendering/           # Étape 4 : Rendering
│   │   ├── step_rendering.py
│   │   ├── make_header.py
│   │   ├── make_main_content.py
│   │   └── make_other.py
│   │
│   └── utils/                    # Utilitaires
│       ├── logging_utils.py
│       ├── logging_utils_test.py
│       ├── llm_utils.py
│       ├── llm_utils_test.py
│       ├── arretify_utils.py
│       ├── documents.py
│       ├── io_utils.py
│       ├── utils.py
│       └── README_LOGGING.md
│
├── data/                         # Données de test (non versionnées)
├── scripts/                      # Scripts utilitaires
├── .env.example                  # Template de configuration
├── .pre-commit-config.yaml       # Configuration pre-commit
├── pyproject.toml                # Configuration du projet
├── LICENSE                       # Licence Apache 2.0
└── README.md                     # Ce fichier
```

**Note** : Les tests sont intégrés dans les modules (`*_test.py`) plutôt que dans un dossier séparé.

## 🧪 Tests

### Lancer les tests

```bash
# Tous les tests
pytest

# Tests avec couverture
pytest --cov=ocapi --cov-report=html

# Tests d'un module spécifique
pytest ocapi/step_chunking/step_chunking_test.py

# Tests en mode verbose
pytest -v
```

### Linting et formatage

```bash
# Black (formatage)
black ocapi/

# isort (import sorting)
isort ocapi/

# Flake8 (linting)
flake8 ocapi/

# Mypy (type checking)
mypy ocapi/

# Tout en une fois (via pre-commit)
pre-commit run --all-files
```

## 📊 Format des données

### Format des fichiers d'entrée

Les arrêtés doivent être au format HTML généré par Arrêtify :

```
YYYY-MM-DD_type_description.html

Exemples :
- 2024-09-27_ap prescriptions complémentaires_description.html
- 2023-12-04_ap d'autorisation_description.html
```

### Structure des répertoires

```
data/
└── <AIOT>/
    └── arretes_html/
        ├── 2009-12-08_ap d'autorisation_....html
        ├── 2014-01-09_ap prescriptions complémentaires_....html
        └── 2024-09-27_ap prescriptions complémentaires_....html
```

### Fichiers de sortie

Le pipeline génère :

```
ocapi_output/
├── operations.json              # Liste des opérations détectées
├── versions/
│   └── history.json            # Historique des versions d'articles
└── permis_consolidé.html       # Permis consolidé final
```

## 🔍 Exemples complets

### Exemple 1 : Traitement complet

```bash
# Traiter tous les arrêtés et générer le permis
ocapi run data/0005804239/arretes_html/ \
    --output data/0005804239/permis.json

# Ou avec main.py
python -m ocapi.main data/0005804239/arretes_html/ \
    --output data/0005804239/ocapi_output/
```

### Exemple 2 : Detection uniquement (pas de rendering)

```bash
python -m ocapi.main data/0005804239/arretes_html/ \
    --no-rendering \
    --output output/detection_only/
```

### Exemple 3 : Filtrage sur arrêtés récents

```bash
ocapi run data/0005804239/arretes_html/ \
    --include 2024-09-27 2023-12-04 \
    --output recent_only.json
```

### Exemple 4 : Mode debug avec logs détaillés

```bash
ocapi --verbose run data/0005804239/arretes_html/

# Rediriger les logs vers un fichier
ocapi --verbose run data/0005804239/arretes_html/ 2>&1 | tee debug.log
```

## 🛠️ Développement

### Ajouter une nouvelle étape au pipeline

1. Créer le dossier `ocapi/step_nouvelleetape/`
2. Implémenter `step_nouvelleetape.py` avec la fonction principale
3. Ajouter les tests dans `step_nouvelleetape_test.py`
4. Intégrer dans `main.py` et `pipeline.py`

### Structure d'une étape

```python
from ocapi.types import ArreteFile
from ocapi.utils.logging_utils import get_logger

logger = get_logger(__name__)

def step_nouvelle_etape(input_data):
    """
    Description de l'étape.
    
    Args:
        input_data: Données en entrée
        
    Returns:
        Résultat de l'étape
    """
    logger.info("Début de l'étape...")
    
    # Traitement
    result = process(input_data)
    
    logger.info(f"Étape terminée: {len(result)} éléments")
    return result
```

## 📝 Logging

OCAPI utilise un système de logging structuré. Voir [README_LOGGING.md](ocapi/utils/README_LOGGING.md) pour plus de détails.

### Configuration du logging

```python
from ocapi.utils.logging_utils import initialize_root_logger

initialize_root_logger(
    level="INFO",              # DEBUG, INFO, WARNING, ERROR, CRITICAL
    log_file="logs/ocapi.log",
    console_output=True,
)
```

### Utilisation dans le code

```python
from ocapi.utils.logging_utils import get_logger

logger = get_logger(__name__)

logger.debug("Message de debug")
logger.info("Message informatif")
logger.warning("Avertissement")
logger.error("Erreur")
logger.exception("Erreur avec traceback")
```

## 🤝 Contribution

1. Fork le projet
2. Créer une branche feature (`git checkout -b feature/amelioration`)
3. Commit les changements (`git commit -m 'Ajout d'une fonctionnalité'`)
4. Push vers la branche (`git push origin feature/amelioration`)
5. Ouvrir une Pull Request

### Standards de code

- **Style** : PEP 8, formaté avec Black (line-length=100)
- **Imports** : Triés avec isort
- **Type hints** : Obligatoires (vérifié avec mypy strict mode)
- **Tests** : Couverture > 80% souhaitée
- **Documentation** : Docstrings pour toutes les fonctions publiques

## 📄 Licence

Copyright (c) 2025 Direction générale de la prévention des risques (DGPR).

Licensed under the Apache License, Version 2.0. See [LICENSE](LICENSE) for details.

## 🔗 Liens utiles

- **Documentation API** : [TODO]
- **Issues** : [TODO]
- **Wiki** : [TODO]

## ❓ FAQ

### Le pipeline échoue avec une erreur de connexion LLM

Vérifiez que :
- La clé API est configurée dans `.env`
- Vous avez accès au réseau PIAG (Si vous utilisez le LLM par défaut)
- Le modèle LLM est disponible

### Comment traiter uniquement certains arrêtés ?

Utilisez l'option `--include` :
```bash
ocapi run data/AIOT/arretes/ --include 2024-09-27 2023-12-04
```

### Comment désactiver le rendering ?

Avec `main.py`, utilisez `--no-rendering` :
```bash
python -m ocapi.main data/AIOT/arretes/ --no-rendering
```

### Les logs affichent trop d'informations

Utilisez l'option `--quiet` pour n'afficher que les warnings et erreurs :
```bash
ocapi --quiet run data/AIOT/arretes/
```
