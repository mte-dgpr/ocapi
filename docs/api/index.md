# API

Référence des modules publics du package `ocapi`. Cette page fait la table des matières ; le détail des signatures vient des docstrings du code (générées via `pdoc`).

## Modules principaux

| Module                       | Rôle                                                                  |
| ---------------------------- | --------------------------------------------------------------------- |
| `ocapi.cli`                  | CLI principal (`ocapi run`, `ocapi update-snapshots`, …).             |
| `ocapi.main`                 | Point d'entrée alternatif (`python -m ocapi.main`).                   |
| `ocapi.pipeline`             | `run_pipeline(...)` : orchestration tagging → detection → resolution → rendering. |
| `ocapi.config`               | Settings Pydantic (`settings`, sous-modèles `LLM`, `Pipeline`, etc.). |
| `ocapi.types`                | Modèles de données (`ArreteFile`, `Operation`, `RawOperation`, `ArticleHistory`, `ErrorCode`, …). |
| `ocapi.exceptions`           | Hiérarchie d'exceptions (`OcapiError`, `OperationError`, `InputOutputError`, …). |
| `ocapi.snapshot`             | Liste des cas snapshot (`SNAPSHOT_CASES`).                            |
| `ocapi.semantic_tag_specs`   | Spec Arrêtify pour la balise `Operation` (utilisée par le tagging).   |

## Étapes du pipeline

| Module                            | Rôle                                                            |
| --------------------------------- | --------------------------------------------------------------- |
| `ocapi.step_tagging`              | Annotation sémantique du HTML Arrêtify ([Tagging](../pipeline-steps/tagging.md)). |
| `ocapi.step_detection`            | Détection LLM des opérations ([Detection](../pipeline-steps/detection.md)).      |
| `ocapi.step_resolution`           | Construction du graphe d'opérations + apply ([Resolution](../pipeline-steps/resolution.md)). |
| `ocapi.step_rendering`            | Génération du permis HTML ([Rendering](../pipeline-steps/rendering.md)).         |

## LLM

| Module                       | Rôle                                                              |
| ---------------------------- | ----------------------------------------------------------------- |
| `ocapi.llm_utils.config`     | Chargement de `config/llm_models.json`, `llm_resilience.json`, `llm_rate_limit.json`. |
| `ocapi.llm_utils.core`       | Appel LLM avec retry / fallback / rate limiting (`call_llm_api`). |
| `ocapi.llm_utils.prompts`    | Templates de prompts (détection, consolidation).                  |
| `ocapi.llm_utils.logging`    | Logs structurés des appels LLM (latence, fallback, erreurs).      |
| `ocapi.llm_utils.mocks`      | Mocks utilisés en test / mode snapshot.                           |

## Utilitaires

| Module                       | Rôle                                                              |
| ---------------------------- | ----------------------------------------------------------------- |
| `ocapi.utils.io_utils`       | Chargement / écriture des arrêtés et JSON (`load_arrete_files`, `save_operations`, `save_history`, `write_permis_output`). |
| `ocapi.utils.tagging_io`     | Conversion HTML taggé → `RawOperation`.                           |
| `ocapi.utils.arretify_utils` | Constantes et helpers Arrêtify (sélecteurs, appendix, sections).  |
| `ocapi.utils.documents`      | Helpers de traitement de documents.                               |
| `ocapi.utils.subtarget_utils`| Localisation et application des sub-targets.                      |
| `ocapi.utils.logging_utils`  | Initialisation du logger applicatif (`initialize_root_logger`).   |
| `ocapi.utils.testing`        | Helpers partagés par les tests (fabriques d'opérations, normalisation HTML). |
| `ocapi.utils.utils`          | Fonctions diverses (`html_checksum`, `strip_none_values`, …).      |

## Génération de la doc API

`pdoc` est inclus dans l'extra `dev`. Pour générer une page HTML statique :

```bash
pip install -e .[dev]
pdoc ocapi -o site/api
```

À terme, intégrer `mkdocstrings` permettrait de mêler signatures auto-générées et prose dans MkDocs ; non branché pour l'instant.

## Stabilité

Le projet est en `Development Status :: 3 - Alpha`. Toutes les API sont susceptibles de changer ; consultez le [CHANGELOG](https://github.com/mte-dgpr/ocapi/releases) (à venir) et les [ADR](../decision-records/index.md) pour les décisions structurantes.
