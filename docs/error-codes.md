# Codes d'erreur

Référence exhaustive des `ErrorCode` produits par OCAPI. Définis dans
[`ocapi/types.py`](https://github.com/mte-dgpr/ocapi/blob/main/ocapi/types.py)
(énumération `ErrorCode` + dict `ERROR_CODE_MESSAGES`).

Les codes circulent à deux niveaux :

- sur les **opérations** (`Operation.error_codes`, sérialisé dans
  `operations.json`) ;
- sur les **versions d'articles** (`ArticleVersion["error_codes"]`, sérialisé
  dans `history.json`).

Le `step_rendering` les utilise pour annoter le permis avec un message
explicite (`ERROR_CODE_MESSAGES`, en français).

## Tableau récapitulatif

| Code (valeur JSON) | Étape qui le pose | Bloque l'application ? | Sens court |
|---|---|---|---|
| `error_extracting_operand` | détection (+ resolution) | oui | Le contenu (operand) n'a pas pu être extrait de l'arrêté modificatif. |
| `error_extracting_source` | resolution (`build_graph`) | oui (pas d'appel LLM) | La section source est introuvable dans le HTML de l'arrêté modificateur. |
| `error_extracting_target` | resolution (`build_graph`) | oui | La section cible est absente, ou abrogation totale du `principal`. |
| `error_finding_subtarget` | resolution (`apply_ops`) | oui | La sous-cible n'a pas été localisée dans l'article cible. |
| `complex_subtarget` | resolution (informatif) | non | Marqueur indiquant qu'une consolidation LLM a été nécessaire ; ne bloque rien. |
| `disabled_llm_call` | resolution (sous-cible complexe + `enable_llm=False`) | oui | La résolution complexe par IA est désactivée (mode snapshot ou opt-out). |
| `propagated_error` | resolution (`apply_ops`) | oui | Une opération précédente sur le même article était en erreur. |
| `less_important` | resolution (`build_graph`) | oui | Abrogation totale écartée car d'autres opérations plus précises ciblent le même arrêté. |
| `missing_arrete` | resolution (`build_graph`) | oui | Toute opération visant un arrêté absent du permis (abrogation totale ou opération article-par-article sur un texte non inclus). |

## Détail par code

### `error_extracting_operand`

**Posé par :**

- la **détection** quand `target_article = "ALL"` est combiné à un `sub_target`
  autre que `FULL_SECTION` (`Operation._derive_detection_error_codes`) — cas
  incohérent côté LLM (« tout l'arrêté » + une portion ciblée à l'intérieur) ;
- l'**extraction d'operand** quand les marqueurs LLM (`new_content_start_marker`
  / `end_marker`) ne se retrouvent pas dans la section source attendue
  (`extract_operand_with_images`).

**Effet :** l'opération est conservée dans `operations.json` pour traçabilité
mais n'est pas appliquée. Le permis affichera un message d'erreur dans la
section modifiante correspondante.

**Pistes de correction :** vérifier la source HTML, ajuster le chunking,
relancer la détection avec un modèle plus capable.

### `error_extracting_source`

**Posé par :** `build_graph` quand `get_node_content(source_id)` lève
`SectionNotFoundError`.

**Effet :** un nœud vide est créé pour l'article source, l'opération est
conservée mais l'application ultérieure (`apply_replace`/`apply_remove`) refuse
d'appeler le LLM dans ce cas (puisque le source manque, prompt sans valeur).

**Pistes :** souvent le signe d'un mauvais découpage de l'arrêté en amont
(Arrêtify) ou d'une référence pointant vers un article hors du périmètre
chargé.

### `error_extracting_target`

**Posé par :**

- `build_graph` quand `get_node_content(target_id)` lève
  `SectionNotFoundError` (la section cible n'existe pas dans le HTML chargé) ;
- `build_graph` quand une **abrogation totale** vise un arrêté marqué
  `principal=True` — c'est presque toujours une fausse détection, on refuse
  d'abroger.

**Effet :** un nœud vide est créé. L'opération reste mais ne produit rien.

**Pistes :** vérifier que le target_arrete fait bien partie des fichiers
chargés ; si l'arrêté principal est concerné, repasser la détection avec un
modèle moins agressif sur les abrogations.

### `error_finding_subtarget`

**Posé par :** `apply_replace` / `apply_remove` quand la sous-cible déclarée
n'est pas localisable, ni par regex ni après tentative LLM.

**Effet :** la version de l'article reste à la dernière version valide ;
l'opération est marquée non résolue.

**Pistes :** souvent dû à un `sub_target.description` trop vague ou à des
divergences de typographie entre la description LLM et le contenu réel
(apostrophes, espaces insécables, abréviations).

### `complex_subtarget`

**Posé par :** trace quand un `sub_target.type == COMPLEX` a été rencontré et
qu'une consolidation LLM a été déclenchée.

**Effet :** **aucun blocage**. Sert d'indicateur, notamment pour estimer
combien d'appels LLM en résolution un cas a nécessité.

### `disabled_llm_call`

**Posé par :** `apply_replace` / `apply_remove` quand un sous-cible complexe
arrive avec `enable_llm=False`.

**Effet :** l'article reste à la version précédente, l'opération est marquée
non résolue. C'est le code attendu en mode **snapshot testing** pour les
opérations qui auraient nécessité un appel LLM.

**Pistes :** rejouer hors snapshot avec `enable_llm=True` pour voir si la
consolidation LLM est correcte ; si oui, le ticket est juste informatif.

### `propagated_error`

**Posé par :** `apply_all_ops` quand on tente d'appliquer une opération sur un
article dont la dernière version porte déjà des `error_codes`.

**Effet :** la nouvelle version sort marquée `propagated_error` (sauf cas
particulier des opérations non ambiguës `_is_unambiguous_all_operation` :
abrogation totale, remplacement total — ces opérations écrasent l'état même
en présence d'erreur précédente).

**Pistes :** corriger l'opération initiale en erreur permettra
mécaniquement de débloquer la chaîne suivante.

### `less_important`

**Posé par :** `build_graph` quand une abrogation totale (REMOVE/REPLACE ALL)
issue d'un arrêté source coexiste avec d'autres opérations du **même** arrêté
source visant le **même** arrêté cible mais sur des sous-parties (articles
nommés). Ces opérations narrower trahissent une fausse détection : si l'arrêté
était réellement abrogé, il ne resterait rien à modifier en détail.

**Effet :** l'abrogation est ignorée — l'arrêté cible n'est pas marqué comme
abrogé et l'opération n'est pas ajoutée au graphe. Les opérations narrower
sont appliquées normalement. Le permis affichera le message « L'arrêté
présente d'autres opérations qui rendent celle-ci caduque ».

### `missing_arrete`

**Posé par :** `build_graph` quand **toute opération** (abrogation totale
REMOVE/REPLACE ALL, ou opération ciblant un article précis) vise un arrêté
qui ne figure pas dans le permis consolidé (typiquement un texte antérieur
non récupéré).

**Effet :** l'opération n'est pas appliquée et n'ajoute aucun nœud au graphe.
Le permis affichera « L'arrêté cible n'est pas présent dans le permis
consolidé » pour signaler qu'il n'y a pas de cible disponible dans le permis.

## Helpers

```python
from ocapi.types import ErrorCode, error_codes_reason, is_resolved_op

is_resolved_op(operation)  # True si error_codes vide
error_codes_reason(frozenset({ErrorCode.PROPAGATED_ERROR}))
# → "Une erreur sur une opération précédente empêche l'application de cette opération"
```

`error_codes_reason` joint plusieurs raisons avec `" ; "`. Quand un code n'a
pas de message dédié, le fallback est `"Opération non résolue automatiquement"`.

## Sérialisation JSON

Dans `operations.json` et `history.json`, les codes sont sérialisés en liste
triée alphabétiquement de leurs `value` :

```json
"error_codes": [
  "error_extracting_operand",
  "propagated_error"
]
```

Un `frozenset` vide est volontairement omis lors de la sortie snapshot
(via `strip_none_values` + filtrage explicite dans `snapshot_test.py`) pour
éviter le bruit dans les diffs.
