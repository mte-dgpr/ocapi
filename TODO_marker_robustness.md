# TODO: Améliorer la robustesse de l'extraction avec markers LLM

## Problème
Le LLM peut générer des markers HTML légèrement incorrects lors de l'extraction d'opérations, ce qui fait échouer `extract_operand_with_images()`.

## Cas identifiés

### 1. Markers avec balises fermantes incorrectes
**Fichier**: `blocs_2023-12-04_bloc_001_llm_output.json`, opérations 3 et 4

**Problème**: Le LLM génère:
- `end_marker: "des VLE.</p></blockquote>"`

Mais dans le HTML réel:
- `"des VLE.</li>"` (suivi de `</ul>` et non `</blockquote>`)

**Cause**: Le LLM suppose/simplifie la structure HTML au lieu de copier exactement les balises du source.

### 2. APPENDIX avec numérotation non trouvée
**Fichier**: `blocs_2024-09-27_bloc_001_llm_output.json`, opération 1

**Problème**: 
- `source_article: "APPENDIX:1.1"`
- Message: "No matching section found for the given source article"

**Cause**: La section APPENDIX:1.1 n'existe peut-être pas dans le HTML ou le format de recherche ne correspond pas.

## Impact actuel
- 3/24 opérations échouent (12.5% de taux d'échec)
- Les opérations échouées sont ignorées et loggées
- Le reste du pipeline continue normalement

## Solutions possibles

### Court terme (Quick fix)
1. **Fuzzy matching des end markers**:
   - Si le marker exact n'est pas trouvé, essayer des variants:
     - Remplacer `</p></blockquote>` par `</p>`, `</li>`, etc.
     - Chercher le texte seul sans les balises
   - Limite: peut matcher incorrectement

2. **Fallback sur le texte seul**:
   - Si le marker HTML complet échoue, chercher juste le texte visible
   - Plus robuste mais moins précis

### Moyen terme (Amélioration du prompt)
1. **Instructions plus strictes dans le prompt**:
   - "Copier EXACTEMENT les balises HTML depuis le bloc source"
   - "Ne pas simplifier ou supposer la structure"
   - Donner des exemples de bons/mauvais markers

2. **Validation post-LLM**:
   - Vérifier que les markers existent réellement dans le HTML source
   - Régénérer avec le LLM si markers invalides

### Long terme (Architecture)
1. **Extraction en 2 passes**:
   - Pass 1: LLM identifie les opérations sans markers
   - Pass 2: Code Python extrait automatiquement les markers corrects

2. **Fallback LLM automatique**:
   - Si marker non trouvé → appel LLM pour ré-extraire juste cette section
   - Plus coûteux mais plus robuste

## Priorité
🔶 **Moyenne** - Le taux d'échec actuel (12.5%) est gérable pour le développement, mais doit être résolu avant production.

## Notes
- Pour l'instant, les opérations échouées sont ignorées et loggées
- Un résumé des erreurs est affiché à la fin de `test_extraction.py`
- Les erreurs sont trackées dans `all_failed_ops` pour analyse ultérieure
