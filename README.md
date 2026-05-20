# OCAPI

**OCAPI** (Outil de Consolidation Automatique des Permis ICPE) est un pipeline de traitement automatisé des arrêtés préfectoraux pour les installations classées pour la protection de l'environnement (ICPE).

## 🎯 Objectif

OCAPI permet de :
- **Détecter** automatiquement les opérations (ajout, modification, suppression) dans les arrêtés
- **Résoudre** les conflits et construire l'historique des articles
- **Générer** un permis consolidé en HTML regroupant toutes les prescriptions applicables

Les exemples ICPE (arrêtés et permis consolidés en HTML) sont consultables dans le navigateur une fois GitHub Pages activé sur la branche `main` (source : répertoire `snapshots/`).

- **Index des exemples** : https://mte-dgpr.github.io/ocapi/snapshots/
- Chaque AIOT dispose de ses arrêtés source et du permis consolidé généré par le pipeline.

## 🏗️ Architecture du pipeline

Le pipeline OCAPI se décompose en 4 étapes principales :

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   STEP 1     │────▶│   STEP 2     │────▶│   STEP 3     │────▶│   STEP 4     │
│   Tagging    │     │  Detection   │     │  Resolution  │     │  Rendering   │
└──────────────┘     └──────────────┘     └──────────────┘     └──────────────┘
 HTML → Tagged       Arrêté → Ops         Ops → History       History → Permis
```

1. **Tagging** : Annote le HTML Arrêtify avec des spans sémantiques d'opérations (verbes, références, sous-cibles)
2. **Detection** : Découpe l'arrêté et détecte les opérations via LLM (ajout, modification, suppression)
3. **Resolution** : Résout les conflits et construit l'historique des versions
4. **Rendering** : Génère le permis consolidé HTML final

### Filtrage des articles superflus

Lors du rendering, les articles dont le titre correspond exactement (comparaison insensible à la casse et aux accents) à un titre qui n'intéresse pas la consolidation (e.g. frais, publication, sanctions…) sont automatiquement exclus du permis consolidé.

## 📦 Installation

### Prérequis

- Python 3.12+
- pip
- [Arrêtify](https://github.com/mte-dgpr/arretify) (installé automatiquement)

### Installation standard

```bash
# Cloner le dépôt
git clone <repository-url>
cd ocapi

# Créer un environnement virtuel

# Windows
py -3.12 -m venv venv
.\venv\Scripts\Activate.ps1

# Linux
python3.12 -m venv venv
source venv/bin/activate

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
LLM__PIAG_API_KEY=votre-clé-api
LLM__PIAG_API_URL=https://preprod.api.piag.e2.rie.gouv.fr/v1/chat/completions

# Placeholder pipeline
PIPELINE__FULL_SECTION=contenu entier

# Logging
LOGGING__LEVEL=INFO
LOGGING__LOG_FILE=logs/ocapi.log
LOGGING__CONSOLE_OUTPUT=true

# Chemins
PATHS__PROJECT_ROOT=/chemin/vers/le/projet
PATHS__CATALOGUE_PATH=/chemin/vers/catalogue_ap.json
```

### 3. Utiliser la configuration dans le code

```python
from ocapi.config import settings

# Accéder aux paramètres
api_key = settings.llm.piag_api_key
full_section = settings.pipeline.full_section
log_level = settings.logging.level
```

### 4. Configuration centralisée des modèles/résilience LLM

La sélection de modèle, le retry, le timeout et le rate limiting sont centralisés
dans des fichiers JSON sous `config/` :

- `config/llm_models.json` (`primary_model_key`, `secondary_model_key`, `models`) ;
  surchargeable sans toucher au JSON via `LLM_PRIMARY_MODEL_KEY` et
  `LLM_SECONDARY_MODEL_KEY` dans le `.env`
- `config/llm_resilience.json` (`timeout_seconds`, stratégie de retry/fallback)
- `config/llm_rate_limit.json` (throttling optionnel)

## 🚀 Usage

OCAPI propose deux interfaces principales :

### 1. CLI officiel (`ocapi`)

Interface en ligne de commande installée globalement :

```bash
# Afficher l'aide
ocapi --help
ocapi run --help

# Traiter tous les arrêtés d'un répertoire
ocapi run snapshots/arretes_html/0005804239/

# Avec options
ocapi run snapshots/arretes_html/0005804239/ \
    --aiot 0005804239 \
    --output resultat.json

# Filtrer sur des arrêtés spécifiques
ocapi run snapshots/arretes_html/0005804239/ \
    --include 2024-09-27 2023-12-04

# Mode verbose
ocapi --verbose run snapshots/arretes_html/0005804239/
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
python -m ocapi.main snapshots/arretes_html/0005804239/

# Répertoire de sortie personnalisé
python -m ocapi.main snapshots/arretes_html/0005804239/ \
    --output custom_output/

# Désactiver la détection (utiliser les opérations préchargées)
python -m ocapi.main snapshots/arretes_html/0005804239/ --no-detection

# Désactiver le rendering (étapes 1-2 uniquement)
python -m ocapi.main snapshots/arretes_html/0005804239/ --no-rendering

# Combiner plusieurs options
python -m ocapi.main snapshots/arretes_html/0005804239/ \
    --include 2024-09-27 2023-12-04 \
    --no-detection \
    --output output/ \
    --verbose
```

**Options supplémentaires :**
- `--no-detection` : Désactiver la détection (utiliser les opérations préchargées)
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
│   ├── step_tagging/             # Étape 1 : Tagging sémantique des opérations
│   │   ├── step_tagging.py
│   │   ├── operations_detection.py
│   │   └── operands_detection.py
│   │
│   ├── step_detection/           # Étape 2 : Détection (chunking + LLM)
│   │   ├── chunking.py
│   │   ├── step_detection.py
│   │   ├── extract_operand.py
│   │   └── prompts.py
│   │
│   ├── step_resolution/          # Étape 3 : Resolution
│   │   ├── step_resolution.py
│   │   ├── apply_ops.py
│   │   └── build_op_graph.py
│   │
│   ├── step_rendering/           # Étape 4 : Rendering
│   │   ├── step_rendering.py
│   │   ├── make_header.py
│   │   ├── make_main_content.py
│   │   └── make_other.py
│   │
│   ├── llm_utils/                # Appels et prompts LLM
│   │   ├── config.py
│   │   ├── core.py
│   │   ├── prompts.py
│   │   ├── logging.py
│   │   └── mocks.py
│   ├── snapshot.py               # Cas de tests snapshot ICPE
│   └── utils/                    # Utilitaires
│       ├── logging_utils.py
│       ├── arretify_utils.py
│       ├── documents.py
│       ├── io_utils.py
│       ├── utils.py
│       └── README_LOGGING.md
│
├── examples/
│   ├── arretes_html/             # Arrêtés HTML par AIOT
│   ├── arretes_operations/       # Opérations détectées (fixtures)
│   ├── ground-truth/             # Opérations annotées manuellement
│   └── consolidated_permit/      # Permis consolidés
├── data/                         # Données de test (non versionnées)
├── scripts/
│   └── evaluate_detection.py     # Évaluation détection vs ground-truth
├── .env.example                  # Template de configuration
├── .pre-commit-config.yaml       # Configuration pre-commit
├── pyproject.toml                # Configuration du projet
├── LICENSE                       # Licence Apache 2.0
└── README.md                     # Ce fichier
```

## 🧪 Tests

### Lancer les tests

```bash
# Tous les tests
pytest

# Tests avec couverture
pytest --cov=ocapi --cov-report=html

# Tests d'un module spécifique
pytest ocapi/step_detection/chunking_test.py

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
ocapi run snapshots/arretes_html/0005804239/ \
    --output output/0005804239/

# Ou avec main.py
python -m ocapi.main snapshots/arretes_html/0005804239/ \
    --output output/0005804239/
```

### Exemple 2 : Detection uniquement (pas de rendering)

```bash
python -m ocapi.main snapshots/arretes_html/0005804239/ \
    --no-rendering \
    --output output/detection_only/
```

### Exemple 3 : Filtrage sur arrêtés récents

```bash
ocapi run snapshots/arretes_html/0005804239/ \
    --include 2024-09-27 2023-12-04 \
    --output recent_only.json
```

### Exemple 4 : Mode debug avec logs détaillés

```bash
ocapi --verbose run snapshots/arretes_html/0005804239/

# Rediriger les logs vers un fichier
ocapi --verbose run snapshots/arretes_html/0005804239/ 2>&1 | tee debug.log
```

### Exemple 5 : Mode snapshot (sans LLM)

Exécuter le pipeline avec des opérations pré-chargées, sans appeler le LLM :

```bash
ocapi run snapshots/arretes_html/0005804239/ \
    --operations-from snapshots/arretes_consolidation/0005804239/ \
    --output output/snapshot/
```

## 📸 Snapshot testing

Des tests de non-régression sur des cas ICPE réels sont disponibles. Ils s'exécutent **sans LLM** (opérations pré-chargées + mock).

```bash
# Exécuter les tests snapshot
pytest -m snapshot -v

# Mettre à jour les snapshots attendus (après modification intentionnelle)
ocapi update-snapshots

# Ou via variable d'environnement
UPDATE_SNAPSHOTS=1 pytest -m snapshot -v
```

Les cas de test sont configurés dans `ocapi/snapshot.py`.

## 📏 Évaluation de la détection

Le script `scripts/evaluate_detection.py` mesure la qualité de la détection des opérations par le LLM en comparant sa sortie aux opérations ground-truth annotées manuellement (dans `examples/ground-truth/`).

Une opération est considérée comme correctement détectée si et seulement si le source (arrêté + article), le target (arrêté + article) et le type d'opération (ADD / REPLACE / REMOVE) correspondent exactement au ground-truth.

Le script produit trois métriques par AIOT et au global : **précision**, **rappel** et **F1-score**.

```bash
# Évaluer sur tous les AIOT avec un modèle donné
python scripts/evaluate_detection.py --model openai_gpt5mini

# Évaluer avec Mistral medium
python scripts/evaluate_detection.py --model mistral_medium

# Restreindre à un AIOT
python scripts/evaluate_detection.py --model openai_gpt5mini --aiot 0003013459

# Mode verbose
python scripts/evaluate_detection.py --model mistral_medium -v
```

Les clés de modèle disponibles sont celles de `config/llm_models.json`.

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

Copyright (c) 2026 Direction générale de la prévention des risques (DGPR).

Licensed under the Apache License, Version 2.0. See [LICENSE](LICENSE) for details.

## 📚 Documentation

La documentation complète est publiée sur GitHub Pages : https://mte-dgpr.github.io/ocapi/

Les sources sont dans le dossier [`docs/`](docs/) (site construit avec MkDocs + Material).

Pour la prévisualiser en local :

```bash
pip install -e .[docs]
mkdocs serve
```

## 🔗 Liens utiles

- **Documentation** : https://mte-dgpr.github.io/ocapi/
- **Exemples ICPE** : https://mte-dgpr.github.io/ocapi/snapshots/
- **Repository** : https://github.com/mte-dgpr/ocapi
- **Issues** : https://github.com/mte-dgpr/ocapi/issues

## ❓ FAQ

### Le pipeline échoue avec une erreur de connexion LLM

Vérifiez que :
- La clé API est configurée dans `.env`
- Vous avez accès au réseau PIAG (Si vous utilisez le LLM par défaut)
- Le modèle LLM est disponible

### Comment traiter uniquement certains arrêtés ?

Utilisez l'option `--include` :
```bash
ocapi run snapshots/arretes_html/<AIOT>/ --include 2024-09-27 2023-12-04
```

### Comment désactiver le rendering ?

Avec `main.py`, utilisez `--no-rendering` :
```bash
python -m ocapi.main snapshots/arretes_html/<AIOT>/ --no-rendering
```

### Les logs affichent trop d'informations

Utilisez l'option `--quiet` pour n'afficher que les warnings et erreurs :
```bash
ocapi --quiet run snapshots/arretes_html/<AIOT>/
```
