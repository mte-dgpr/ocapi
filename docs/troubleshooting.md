# Dépannage

Erreurs courantes, limitations connues et pistes de résolution. Pour les codes d'erreur attachés aux opérations et versions d'articles, voir [Codes d'erreur](error-codes.md).

## Erreurs LLM

### Connexion / authentification (PIAG)

**Symptômes :** `requests.exceptions.ConnectionError`, `401 Unauthorized`, `403 Forbidden` au démarrage de la détection.

À vérifier :

- `LLM__PIAG_API_KEY` est défini (`echo $LLM__PIAG_API_KEY`).
- `LLM__PIAG_API_URL` pointe sur l'instance attendue (`preprod` vs `prod`).
- Tu es bien sur le réseau PIAG (VPN / poste interne).
- Le modèle ciblé existe dans `config/llm_models.json` (`primary_model_key`).

Workaround : tu peux rejouer un cas en mode snapshot via `--operations-from` ([Usage](usage.md#mode-snapshot-sans-llm)) sans appel LLM.

### Timeouts et retries

Les paramètres sont centralisés dans `config/llm_resilience.json` (`timeout_seconds`, stratégie de retry/fallback). Voir [LLM](llm.md).

Si la cible LLM répond lentement :

- augmente `timeout_seconds` ;
- vérifie `config/llm_rate_limit.json` (un rate limit trop bas peut empiler des attentes) ;
- bascule sur `secondary_model_key` (modèle de repli automatique).

### Réponses inattendues du modèle

Le LLM peut renvoyer du JSON invalide ou des champs manquants. Le pipeline marque alors les opérations concernées avec un `error_codes` (`ERROR_EXTRACTING_OPERAND`, `ERROR_EXTRACTING_TARGET`, `ERROR_EXTRACTING_SOURCE`, `COMPLEX_SUBTARGET`, etc.).

- Lance avec `--verbose` et inspecte les warnings `step_detection`.
- Les opérations en erreur restent dans `operations.json` et leur impact est tracé dans `history.json` (voir [Codes d'erreur](error-codes.md)).
- En cas de régression sur un cas connu, regarde `scripts/evaluate_detection.py` pour mesurer l'écart au ground-truth.

## Détection imprécise

- Vérifie que les fichiers HTML sont bien produits par Arrêtify (sinon `validate_arretify_version` les exclut au chargement).
- Le LLM s'appuie sur la segmentation Arrêtify : un découpage en sections incorrect dégrade les résultats. Inspecte le HTML d'entrée.
- Les opérations détectées avec `error_codes = [COMPLEX_SUBTARGET]` indiquent que le sub-target nécessite une consolidation LLM au moment du resolution. Pas une erreur en soi.

## Resolution : opérations non appliquées

Les opérations en erreur sont conservées mais ne modifient pas l'historique. Cas typiques :

- `ERROR_EXTRACTING_OPERAND` : pas de contenu de remplacement → la version reste inchangée et hérite de l'erreur.
- `ERROR_FINDING_SUBTARGET` : la sous-cible (paragraphe, phrase) n'a pas été trouvée dans l'article cible.
- `PROPAGATED_ERROR` : la version précédente était déjà en erreur ; les opérations suivantes héritent du statut sauf bypass `REPLACE`/`REMOVE` sur `FULL_SECTION`.
- `DISABLED_LLM_CALL` : opération `COMPLEX_SUBTARGET` rencontrée alors que `enable_llm=False` (mode snapshot).

Voir [Pipeline / Resolution](pipeline-steps/resolution.md) pour la logique de propagation.

## Rendering : permis vide ou incomplet

- Vérifie que `--no-rendering` n'est pas actif.
- Si tous les articles d'un AIOT ont un `error_codes` non vide, le permis peut être quasi vide. Inspecte `history.json`.
- Les articles dont le titre matche les patterns "filtre" (frais, publication, sanctions…) sont volontairement exclus. Liste dans `ocapi/step_rendering/article_filter.py`.
- Aucun arrêté principal détecté ? Marque-en un explicitement avec `--principal-id`.

## Snapshot tests qui échouent

```text
AssertionError: Snapshot mismatch: operations.json
```

Régénère les snapshots si la divergence est attendue :

```bash
ocapi update-snapshots
# ou
UPDATE_SNAPSHOTS=1 pytest -m snapshot
```

Si la divergence est inattendue, compare l'écart manuellement :

```bash
git diff snapshots/arretes_consolidation/<AIOT>/
```

Voir [Snapshot testing](snapshot-testing.md).

## Erreurs de chargement des arrêtés

| Symptôme                                                        | Cause probable                                                                                |
| --------------------------------------------------------------- | --------------------------------------------------------------------------------------------- |
| `InputOutputError: Input directory does not exist`              | Mauvais chemin passé en argument.                                                             |
| `InputOutputError: No HTML files found`                         | Le dossier ne contient aucun `*.html`.                                                        |
| `WARNING File skipped (invalid format)`                         | Le nom de fichier ne respecte pas `YYYY-MM-DD_<type>_*.html`. Voir [Usage](usage.md).          |
| `WARNING File skipped (incompatible Arrêtify version)`          | Le HTML a été produit par une version d'Arrêtify hors `~=0.2.0`. Voir [ADR 0004](decision-records/0004-arretify-version-pin.md). |
| `WARNING File excluded (non-AP type)`                           | Le filename matche un pattern exclu (rapport, fiche Seveso, mise en demeure, etc.).            |

## Documentation locale ne sert pas

```bash
mkdocs serve
# zsh: command not found: mkdocs
```

L'extra `docs` n'est pas installé :

```bash
pip install -e .[docs]
```

## Limitations connues

- **Coût LLM** : `ocapi run` sans `--operations-from` appelle systématiquement le LLM pour chaque arrêté. Privilégie les snapshots en CI.
- **Sub-targets complexes** : le rendu des modifications partielles (phrase, alinéa, ligne d'un tableau) repose sur un fallback LLM. Désactivé en mode snapshot (`DISABLED_LLM_CALL`).
- **Filtre d'articles** : la liste de patterns dans `article_filter.py` est statique. Toute évolution réglementaire demande une mise à jour manuelle.
- **Multi-AIOT** : OCAPI traite un AIOT à la fois. Pour batcher, scripte une boucle shell autour de `ocapi run`.
- **Arrêtify 0.2.x** : version épinglée. Bumper Arrêtify nécessite de régénérer les fixtures snapshot et de revalider la chaîne (cf. ADR 0004).

Voir aussi [Roadmap](roadmap.md) pour les évolutions identifiées.
