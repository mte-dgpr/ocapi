# OCAPI

TODO: Courte description du projet.


## Configurer son environnement de développement

TODO: Add conf steps and switch to english

```bash
# Créer un environnement virtuel
python -m venv venv
source venv/bin/activate   # Windows : venv\Scripts\activate

# Installer les dépendances de dev
pip install --upgrade pip
pip install .[dev]

# Activer les hooks pre-commit
pre-commit install
```

## Configuration

OCAPI utilise **Pydantic Settings** pour une configuration typée et validée.

```bash
# 1. Créer un fichier .env (voir config.env.example)
cp config.env.example .env

# 2. Ajouter vos clés API
PIAG_API_KEY=votre-clé

# 3. Utiliser dans le code
from ocapi.config import settings
```