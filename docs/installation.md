# Installation

## Prérequis

- **Python 3.12 ou 3.13** (`requires-python = ">=3.12"` dans `pyproject.toml`).
- **`pip`** récent (`pip install --upgrade pip`).
- **Git** pour cloner le dépôt.
- Accès au réseau **PIAG** si tu utilises les modèles LLM par défaut (voir [Configuration](configuration.md)).
  Sans ce réseau, OCAPI reste utilisable en mode `--operations-from` (snapshot) ou avec un autre fournisseur LLM configuré dans `config/llm_models.json`.

[Arrêtify](https://github.com/mte-dgpr/arretify) (~0.2.x) est installé automatiquement comme dépendance.

## Installation standard (utilisation)

=== "Linux / macOS"

    ```bash
    git clone https://github.com/mte-dgpr/ocapi.git
    cd ocapi

    python3.12 -m venv .venv
    source .venv/bin/activate

    pip install --upgrade pip
    pip install -e .
    ```

=== "Windows"

    ```powershell
    git clone https://github.com/mte-dgpr/ocapi.git
    cd ocapi

    py -3.12 -m venv venv
    .\venv\Scripts\Activate.ps1

    pip install --upgrade pip
    pip install -e .
    ```

L'installation expose deux entry points :

- `ocapi` — CLI principal ([Référence CLI](cli-reference.md))
- `flake` — alias local pour `flake8` (raccourci de dev)

## Installation pour le développement

Ajoute l'extra `dev` (linters, mypy, pytest, pre-commit) :

```bash
pip install -e .[dev]
pre-commit install
```

Pour aussi prévisualiser la documentation localement, ajoute `docs` :

```bash
pip install -e .[dev,docs]
```

Versions épinglées dans l'extra `dev` (`pyproject.toml`) :

| Outil          | Version |
| -------------- | ------- |
| `black`        | 25.1.0  |
| `isort`        | 5.13.2  |
| `flake8`       | 7.2.0   |
| `autoflake`    | 2.3.1   |
| `mypy`         | ≥ 1.13  |
| `pre-commit`   | ≥ 3.8   |
| `pytest`       | ≥ 8.3   |

## Vérification

```bash
ocapi --version
ocapi --help
pytest --no-cov -q
```

Pour prévisualiser la documentation :

```bash
mkdocs serve
```

## Mises à jour

```bash
git pull
pip install -e .[dev,docs]   # réinstalle si l'extra a changé
```

## Désinstallation

```bash
pip uninstall ocapi
deactivate
rm -rf .venv
```

## Pièges courants

- **Python < 3.12** : `pip install -e .` échoue (`requires-python`). Crée un venv avec `python3.12` ou `py -3.12`.
- **`mkdocs serve` indisponible** : il faut l'extra `docs` (`pip install -e .[docs]`).
- **Hooks pre-commit non lancés** : `pre-commit install` n'a pas été exécuté après le clone.
- **`arretify` incompatible** : OCAPI épingle `arretify~=0.2.0`. Voir [ADR 0004](decision-records/0004-arretify-version-pin.md).
