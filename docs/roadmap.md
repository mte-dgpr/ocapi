# Roadmap

Inventaire des chantiers identifiés mais non terminés au moment de la
passation. Sert de point de départ pour la suite. À mettre à jour au fil
des décisions.

> Cette page est un **document vivant**. Quand un item est traité, déplacer la
> ligne vers la section « Fait » avec un lien vers le PR ou le commit. Quand
> une priorité change, éditer.

## Court terme

### Détection

- **Améliorer la robustesse aux variantes de formulation** — le prompt couvre
  les verbes courants mais rate encore certaines tournures composées
  (« il est procédé à l'abrogation et à la substitution »). Construire un
  ground-truth dédié pour ces cas et itérer sur le prompt
  ([`ocapi/llm_utils/prompts.py`](https://github.com/mte-dgpr/ocapi/blob/main/ocapi/llm_utils/prompts.py)).
- **Évaluation par opération typée** — le matching actuel ignore l'operand et
  la sub_target (cf. [Évaluation § Limites](evaluation.md#limites)). Ajouter
  une métrique secondaire qui les inclue.

### Resolution

- **Sous-cibles complexes sans LLM** — beaucoup de `COMPLEX` sont en réalité
  résolubles par des règles plus riches (regex multi-segment, fuzzy match,
  reconnaissance de tableau). Réduire le taux d'appel LLM en résolution
  améliorerait coût et déterminisme.
- **Cycles dans le graphe** — actuellement non détectés explicitement
  (cf. [Resolution § Cas limites](pipeline-steps/resolution.md#cas-limites-connus)).
  Ajouter un check `nx.find_cycle` + diagnostic.

### Rendering

- **Filtres d'articles superflus configurables** — la liste est en dur dans
  [`article_filter.py`](https://github.com/mte-dgpr/ocapi/blob/main/ocapi/step_rendering/article_filter.py).
  La déplacer dans `config/` permettrait à un opérateur d'ajuster sans
  release.
- **Annotations d'opérations dans le permis** — l'injection actuelle
  (`build_source_operation_messages`) est minimaliste. Améliorer la
  présentation visuelle (icônes par `ErrorCode`, lien vers l'arrêté source).

## Moyen terme

### Pipeline

- **Étape `step_tagging` upstream** — actuellement portée localement
  (cf. [ADR 0004](decision-records/0004-arretify-version-pin.md) et docstring
  de `step_tagging.py`). Quand Arrêtify expose le module en public, supprimer
  la copie OCAPI et réimporter.
- **Pipeline incrémental** — pour le moment chaque run reprend tout depuis
  zéro. Permettre de réutiliser un `history.json` existant pour ne traiter
  que les arrêtés ajoutés depuis.
- **Génération de l'API doc** — l'extra `pdoc` est déclaré dans `pyproject.toml`
  mais non branché ; en tirer une `docs/api/` automatique via mkdocstrings ou
  pdoc + workflow Pages.

### LLM

- **Cache de réponses LLM** — sur les benchmarks, on rejoue souvent les mêmes
  prompts. Un cache local (clé = hash du prompt + modèle) accélérerait
  l'itération.
- **Streaming des réponses** — gain marginal en latence ressentie pour les
  longs blocs.
- **Provider Anthropic / Gemini en condition réelle** — l'intégration existe
  mais n'a pas été testée massivement. Faire une éval comparative sur tous
  les AIOTs ground-truth.

### Tooling

- **Snapshot tests étendus** — actuellement 4 AIOTs. Ajouter 2-3 cas
  pathologiques (refonte, abrogation totale, beaucoup de COMPLEX) pour
  durcir la couverture.
- **Pre-commit `mkdocs build --strict`** — désactivé tant que la doc est en
  stub, à activer quand la majorité des pages est rédigée pour éviter les
  liens cassés en review.
- **CI : badge couverture, badge éval F1** — déjà des artefacts CI ; les
  exposer en README.

## Long terme

- **Pipeline parallèle par arrêté** — les détections sont indépendantes ; un
  thread/process pool diviserait le temps de bout en bout.
- **UI** — visualiseur de différences arrêté ↔ permis consolidé, navigation
  par opération, validation interactive du ground-truth.
- **Multi-AIOT par run** — actuellement un AIOT à la fois. Pertinent surtout
  pour le batch nocturne.
- **Format de sortie alternatif** — JSON-LD ou XML structuré, pour intégration
  dans GUN ou autre SI ICPE.

## À suivre / dette technique

- `arretes_consolidation/`, `arretes_tagged/` et `output/` non versionnés mais
  présents en local — vérifier que `.gitignore` couvre tout.
- Doublons `… 2.py`, `… 2.json` apparus suite à des conflits de sync (iCloud /
  copie d'arborescence) — nettoyer une bonne fois.
- `cli_flake.py` est un alias local à `flake8` ; à supprimer si l'équipe
  bascule sur `ruff` ou un autre linter.
- `ocapi/utils/README_LOGGING.md` partiellement repris dans
  [`docs/logging.md`](logging.md) — à terme, supprimer le README pour ne
  garder qu'une source de vérité.
- `ocapi/utils/documents.py` contient un TODO « replace this file with
  PY-arrete_utils when the library is ready ».

## Idées non prioritaires

- Export `permis.html` en PDF via wkhtmltopdf / playwright.
- Comparaison automatique entre permis OCAPI et permis manuel existant
  (alignement et diff article par article).
- Détection automatique des `principal=True` (au lieu de devoir le passer
  manuellement à la CLI).

## Fait

- Mise en place de la doc MkDocs + Material — voir
  [`docs/`](https://github.com/mte-dgpr/ocapi/tree/main/docs).

> Ajouter ici les items terminés au fil de l'eau, avec lien vers le PR.
