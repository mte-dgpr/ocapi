# Contribuer

## Workflow Git

- Branche depuis `main` : `git checkout -b feat/<sujet>` ou `fix/<sujet>`.
- Une branche = une PR ciblée. Évite les PR fourre-tout.
- Rebase sur `main` avant ouverture (`git fetch origin && git rebase origin/main`).
- Pousse, ouvre la PR sur GitHub, attache le contexte (issue, capture d'écran, snapshot diff).
- Demande la revue ; ne ferme pas les threads de revue toi-même (les reviewers les marquent comme résolus).

### Messages de commit

Convention courte du dépôt (cf. `.cursor/rules/commit-messages.mdc`) :

- une ligne unique, **7 mots maximum** ;
- pas de corps, pas de référence d'issue dans le commit (les outils de tracking suffisent) ;
- formulation factuelle : `add retry for piag timeout`, `fix null check in renderer`, `remove unused helper`.

## Standards de code

- **Python 3.12**, type hints obligatoires (mypy strict via `pyproject.toml`).
- **Black** pour le formatage (`line-length = 100`).
- **isort** profil `black`.
- **flake8** + `flake8-bugbear` (`extend-select = ["I", "B"]`).
- **autoflake** retire les imports inutiles.
- Commentaires courts, en anglais, au présent (cf. `.cursor/rules/code-comments.mdc`). Pas de numéros de ticket.
- Pas d'attribution AI / outil dans le code, les commentaires ou les commits.

## Tests

Tous les modules portent leurs tests à côté (`*_test.py`). `pytest` les ramasse via `python_files = ["*_test.py"]`.

```bash
# Tout
pytest

# Module ciblé
pytest ocapi/step_resolution/

# Sans couverture (plus rapide en dev)
pytest --no-cov -q

# Snapshots
pytest -m snapshot
UPDATE_SNAPSHOTS=1 pytest -m snapshot   # régénère
```

Couverture minimale : **80 %** (configurée dans `addopts`).

## Lint et formatage

```bash
black ocapi/
isort ocapi/
flake8 ocapi/      # ou : flake ocapi/
mypy ocapi/
```

Tout en une passe :

```bash
pre-commit run --all-files
```

## Pre-commit

Une fois `pre-commit install` exécuté (cf. [Installation](installation.md)), chaque commit déclenche : `check-merge-conflict`, `end-of-file-fixer`, `trailing-whitespace`, `check-yaml --unsafe`, `check-json`, `licenseheaders`, `black`, `isort`, `autoflake`, `flake8`, `mypy`, `pytest`.

`mypy` et `pytest` allongent le commit (~30–60 s). Ne pas désactiver les hooks (`--no-verify`) sans raison explicite.

## CI

GitHub Actions exécute :

- `lint` : black + isort + flake8 + mypy ;
- `unit-tests` : `pytest` (couverture incluse).

La PR doit être verte avant merge.

## Cycle de revue

- Réponds aux commentaires en poussant un commit additionnel ; ne réécris pas l'historique tant que la PR est en revue.
- N'utilise pas "Resolve conversation" : c'est au reviewer de fermer ses propres threads (cf. `.cursor/rules/pr-review-threads.mdc`).
- Si une remarque demande un changement structurel hors scope, ouvre une issue de suivi plutôt que d'élargir la PR.

## Ajouter une nouvelle étape au pipeline

1. Crée le dossier `ocapi/step_<nom>/` avec un `__init__.py` qui réexporte la fonction publique.
2. Implémente `step_<nom>.py` (signature : entrée → sortie typée explicitement).
3. Ajoute les tests `step_<nom>_test.py` à côté.
4. Branche l'étape dans `ocapi/pipeline.py` (et `ocapi/main.py` / `ocapi/cli.py` si une option est exposée).
5. Documente dans `docs/pipeline-steps/<nom>.md` et mets à jour `mkdocs.yml`.
6. Mets à jour [Architecture](architecture.md) (au moins le diagramme et la table des étapes).

## Ajouter ou modifier la documentation

- Les sources sont dans `docs/`. La nav est définie dans `mkdocs.yml`.
- Test local :

  ```bash
  pip install -e .[docs]
  mkdocs serve
  ```

- La CI publie automatiquement sur GitHub Pages à chaque push sur `main` touchant `docs/`, `mkdocs.yml` ou `snapshots/`.

## Décisions structurantes : ADR

Si tu prends une décision non triviale (choix de techno, refonte d'API, nouveau format), crée un ADR dans `docs/decision-records/` numéroté à la suite (`000X-<slug>.md`). Format : contexte, décision, alternatives, conséquences. Exemples : [0001](decision-records/0001-three-step-pipeline.md), [0004](decision-records/0004-arretify-version-pin.md).
