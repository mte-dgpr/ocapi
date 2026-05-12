# Architecture

Vue d'ensemble du pipeline OCAPI : ce qui entre, ce qui sort, et comment les étapes
s'enchaînent.

## Vue d'ensemble

OCAPI prend en entrée un ensemble d'arrêtés préfectoraux **déjà tagués au format
[Arrêtify](https://github.com/mte-dgpr/arretify)** pour un même AIOT, et produit
un **permis consolidé HTML** qui regroupe les prescriptions toujours applicables.

Le pipeline est une fonction pure de bout en bout :

```mermaid
flowchart LR
  inputs["Arrêtés HTML Arrêtify<br/>pour un AIOT"] --> tagging["Step 1<br/>Tagging"]
  tagging --> detection["Step 2<br/>Detection"]
  detection --> resolution["Step 3<br/>Resolution"]
  resolution --> rendering["Step 4<br/>Rendering"]
  rendering --> permis["permis.html"]
  tagging -.->|tagged HTML| snapshot[("snapshots")]
  detection -.->|operations.json| snapshot
  resolution -.->|history.json| snapshot
```

Le point d'entrée principal est [`run_pipeline`](https://github.com/mte-dgpr/ocapi/blob/main/ocapi/pipeline.py)
dans [`ocapi/pipeline.py`](https://github.com/mte-dgpr/ocapi/blob/main/ocapi/pipeline.py).

## Étapes

| Étape | Module | Entrée | Sortie | LLM |
|---|---|---|---|---|
| 1. [Tagging](pipeline-steps/tagging.md) | `ocapi/step_tagging/` | `DocumentContext` | `DocumentContext` annoté | non |
| 2. [Detection](pipeline-steps/detection.md) | `ocapi/step_detection/` | `ArreteFile` | `list[Operation]` | oui |
| 3. [Resolution](pipeline-steps/resolution.md) | `ocapi/step_resolution/` | `list[Operation]` + `list[ArreteFile]` | `ArticleHistory` | optionnel |
| 4. [Rendering](pipeline-steps/rendering.md) | `ocapi/step_rendering/` | `ArticleHistory` + arrêtés + opérations | `Permis` (HTML) | non |

La détection et le rendering peuvent être désactivés via `run_pipeline(...)`
(`enable_detection=False`, `enable_rendering=False`) ou les flags équivalents
de la CLI. C'est ce qui permet le mode **snapshot** (rejouer le pipeline sans
LLM à partir d'un `operations.json` figé).

## Modèle de données

Les types vivent dans [`ocapi/types.py`](https://github.com/mte-dgpr/ocapi/blob/main/ocapi/types.py).
Les principaux :

- `ArreteFile` — un arrêté chargé : `id` (date `YYYY-MM-DD`), `aiot`, `filename`,
  `soup` (BeautifulSoup), `file_type`, `status` (devient `False` si abrogé),
  `principal` (flag pour la consolidation).
- `NodeId` — identifiant unique d'un article : `(arrete_id, article_id)`.
  `article_id` peut être un numéro pointé (`1.2`, `I.1`, `A-3`) ou un mot-clé
  (`ALL`, `END`, `APPENDIX`, `APPENDIX:1.2`, `NEW_ARTICLE:1.2`).
- `Operation` — opération typée détectée : `id`, `source_id`, `target_id`,
  `operation_type` (`ADD` / `REPLACE` / `REMOVE`), `operand`, `sub_target`,
  `error_codes`, `confidence_score`.
- `ArticleHistory` — `Dict[NodeId, list[ArticleVersion]]`. Chaque version a
  `version`, `title`, `content`, `operation_id`, `error_codes`.
- `Permis` — trois fragments HTML (`header`, `contenu`, `other`) injectés dans
  le template [`templates/permis_consolide.html`](https://github.com/mte-dgpr/ocapi/blob/main/templates/permis_consolide.html).
- `ErrorCode` — énumération typée d'erreurs de résolution propagées sur les
  opérations puis sur les versions d'articles (voir [Resolution](pipeline-steps/resolution.md)).

## Artefacts

Pour un AIOT donné, le pipeline écrit (par défaut sous
`arretes_consolidation/<aiot>/`) :

- `operations.json` — liste sérialisée des `Operation`. Sert d'entrée au mode
  snapshot.
- `history.json` — `ArticleHistory` sérialisée.
- `permis.html` — permis consolidé final.

En parallèle, si `step_tagging` est actif, les HTMLs taggués sont écrits sous
`arretes_tagged/<aiot>/`.

## Dépendances externes

- **[Arrêtify](https://github.com/mte-dgpr/arretify)** — produit le HTML
  sémantique en entrée (sections, articles, visas, motifs, annexes, …) et
  fournit `DocumentContext`. La version supportée est verrouillée (cf.
  `SUPPORTED_ARRETIFY_VERSION` dans [`ocapi/config.py`](https://github.com/mte-dgpr/ocapi/blob/main/ocapi/config.py)).
- **LLM** — un fournisseur parmi PIAG / OpenAI / Mistral / Anthropic / Google,
  appelé pendant la détection (et marginalement pendant la résolution pour les
  sous-cibles complexes). Voir [LLM](llm.md).
- **`networkx`** — graphe orienté multi-arêtes des opérations construit pendant
  la résolution.

## Cartographie complète du code

Vue détaillée des modules, des dépendances internes et de la place des fichiers
de config et de templates.

```mermaid
flowchart TB
  subgraph entry [Entrées]
    cli["ocapi/cli.py<br/>console_script ocapi"]
    main["ocapi/main.py<br/>python -m ocapi.main"]
    flake["ocapi/cli_flake.py<br/>console_script flake"]
  end

  subgraph orch [Orchestration]
    pipeline["ocapi/pipeline.py<br/>run_pipeline"]
  end

  subgraph steps [Étapes du pipeline]
    tagging["step_tagging/<br/>step_tagging.py<br/>operations_detection.py<br/>operands_detection.py"]
    detection["step_detection/<br/>step_detection.py<br/>chunking.py<br/>extract_operand.py"]
    resolution["step_resolution/<br/>step_resolution.py<br/>build_op_graph.py<br/>apply_ops.py"]
    rendering["step_rendering/<br/>step_rendering.py<br/>header.py<br/>main_content.py<br/>other.py<br/>article_filter.py<br/>operation_messages.py"]
  end

  subgraph llm [LLM]
    llm_init["llm_utils/__init__.py"]
    llm_cfg["llm_utils/config.py"]
    llm_core["llm_utils/core.py<br/>retry, fallback, rate-limit"]
    llm_prompts["llm_utils/prompts.py"]
    llm_logging["llm_utils/logging.py"]
    llm_mocks["llm_utils/mocks.py"]
  end

  subgraph data [Modèle de données]
    types["types.py<br/>ArreteFile NodeId Operation<br/>ArticleHistory Permis ErrorCode"]
    semspec["semantic_tag_specs.py<br/>OperationSpec / OperationData"]
    excs["exceptions.py<br/>OcapiError + sous-classes"]
    appcfg["config.py<br/>AppConfig Pydantic Settings"]
  end

  subgraph utils [Utils transverses]
    io["utils/io_utils.py"]
    arr["utils/arretify_utils.py"]
    docs_u["utils/documents.py"]
    sub["utils/subtarget_utils.py"]
    log["utils/logging_utils.py"]
    tagio["utils/tagging_io.py"]
    err["utils/error_handling.py"]
    ut["utils/utils.py"]
    test_u["utils/testing.py"]
  end

  subgraph snap [Snapshot]
    snapcfg["snapshot.py<br/>SNAPSHOT_CASES"]
    snaptest["snapshot_test.py"]
  end

  subgraph cfg [Config externe]
    env[".env<br/>Pydantic Settings"]
    models["config/llm_models.json"]
    resil["config/llm_resilience.json"]
    rate["config/llm_rate_limit.json"]
    tpl["templates/permis_consolide.html"]
  end

  subgraph scripts_g [Scripts]
    eval["scripts/evaluate_detection.py"]
    gendocs["scripts/generate_docs_index.py"]
  end

  cli --> pipeline
  main --> pipeline
  pipeline --> tagging
  pipeline --> detection
  pipeline --> resolution
  pipeline --> rendering

  tagging --> semspec
  detection --> llm_init
  detection --> types
  resolution --> llm_init
  resolution --> types
  resolution --> sub
  rendering --> types
  rendering --> arr

  llm_init --> llm_cfg
  llm_init --> llm_core
  llm_init --> llm_prompts
  llm_core --> llm_logging
  llm_cfg --> appcfg
  llm_cfg --> models
  llm_core --> resil
  llm_core --> rate

  types --> appcfg
  types --> excs
  appcfg --> env
  rendering --> tpl

  cli --> io
  main --> io
  io --> types
  io --> arr
  io --> docs_u
  io --> tagio

  detection --> arr
  detection --> docs_u
  rendering --> log
  resolution --> log

  eval --> detection
  eval --> llm_init
  snaptest --> snapcfg
  snaptest --> pipeline
  snaptest --> io
```

Lecture rapide :

- **Entrées** (CLI + module main) ne connaissent qu'`io_utils`, `pipeline.run_pipeline`
  et la config Pydantic.
- **`pipeline.py`** est la seule colle entre les étapes — chaque étape ignore les
  autres.
- **`llm_utils/`** est isolé : `step_detection` et `step_resolution` n'importent
  que son `__init__` (qui sert de façade).
- **`utils/`** est partagé mais sans import croisé entre étapes.
- **Config externe** (`.env`, JSON, template) est lue à travers
  [`config.py`](https://github.com/mte-dgpr/ocapi/blob/main/ocapi/config.py)
  ou [`llm_utils/config.py`](https://github.com/mte-dgpr/ocapi/blob/main/ocapi/llm_utils/config.py).
- **Snapshots** sont un cas particulier : `snapshot_test.py` réutilise
  `run_pipeline` avec `enable_detection=False` + `enable_llm=False`.

## Décisions associées

- [ADR 0001 — Pipeline en étapes explicites](decision-records/0001-three-step-pipeline.md)
- [ADR 0002 — Détection par LLM](decision-records/0002-llm-for-detection.md)
- [ADR 0003 — Snapshot testing](decision-records/0003-snapshot-testing.md)
- [ADR 0004 — Pinning de la version Arrêtify](decision-records/0004-arretify-version-pin.md)
- [ADR 0005 — Pydantic Settings + double config](decision-records/0005-pydantic-settings-dual-config.md)
