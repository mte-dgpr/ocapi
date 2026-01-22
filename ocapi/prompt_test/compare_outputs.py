"""
Compare les outputs du LLM avec les expected outputs et affiche les différences.
"""

import json
from pathlib import Path
from typing import Any, Dict, List
from difflib import unified_diff


PROJECT_ROOT = Path(__file__).resolve().parents[2]
EXPECTED_DIR = PROJECT_ROOT / "ocapi" / "prompt_test" / "expected_results"
LLM_OUTPUT_DIR = PROJECT_ROOT / "ocapi" / "prompt_test" / "llm_output"


def load_json(file_path: Path) -> List[Dict[str, Any]]:
    """Charge un fichier JSON."""
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def compare_operation(expected: Dict, actual: Dict, op_index: int) -> List[str]:
    """Compare une opération expected avec actual et retourne les différences."""
    differences = []
    
    for key in expected.keys():
        expected_val = expected.get(key)
        actual_val = actual.get(key)
        
        if expected_val != actual_val:
            differences.append(f"  ❌ {key}:")
            differences.append(f"      Expected: {expected_val}")
            differences.append(f"      Actual:   {actual_val}")
    
    return differences


def compare_files(expected_file: Path, llm_file: Path) -> Dict[str, Any]:
    """Compare deux fichiers JSON et retourne les statistiques et différences."""
    
    if not llm_file.exists():
        return {
            "status": "missing",
            "message": f"❌ Fichier LLM manquant: {llm_file.name}"
        }
    
    expected_ops = load_json(expected_file)
    actual_ops = load_json(llm_file)
    
    result = {
        "status": "ok",
        "file": expected_file.name,
        "expected_count": len(expected_ops),
        "actual_count": len(actual_ops),
        "differences": [],
        "false_positives": []
    }
    
    # Cas spécial: expected = [] mais actual != []
    if len(expected_ops) == 0 and len(actual_ops) > 0:
        result["status"] = "false_positive"
        result["differences"].append(
            f"🚨 FAUX POSITIFS: Expected = liste vide, mais {len(actual_ops)} opération(s) trouvée(s)"
        )
        result["differences"].append("")
        result["differences"].append("Opérations générées à tort:")
        for i, op in enumerate(actual_ops):
            result["differences"].append(f"\n  Opération {i+1}:")
            result["differences"].append(f"    - operation_type: {op.get('operation_type')}")
            result["differences"].append(f"    - source_article: {op.get('source_article')}")
            result["differences"].append(f"    - target_article: {op.get('target_article')}")
            result["differences"].append(f"    - target_arrete: {op.get('target_arrete')}")
            result["differences"].append(f"    - sub_target: {op.get('sub_target')}")
            result["false_positives"].append(op)
        return result
    
    # Cas spécial: expected != [] mais actual = []
    if len(expected_ops) > 0 and len(actual_ops) == 0:
        result["status"] = "false_negative"
        result["differences"].append(
            f"🚨 FAUX NÉGATIFS: Expected = {len(expected_ops)} opération(s), mais liste vide trouvée"
        )
        return result
    
    # Comparer le nombre d'opérations
    if len(expected_ops) != len(actual_ops):
        result["status"] = "error"
        result["differences"].append(
            f"⚠️  Nombre d'opérations différent: {len(expected_ops)} attendues, {len(actual_ops)} trouvées"
        )
    
    # Comparer chaque opération
    for i, expected_op in enumerate(expected_ops):
        if i >= len(actual_ops):
            result["status"] = "error"
            result["differences"].append(f"❌ Opération {i+1} manquante dans l'output LLM")
            continue
        
        actual_op = actual_ops[i]
        op_diffs = compare_operation(expected_op, actual_op, i)
        
        if op_diffs:
            result["status"] = "error"
            result["differences"].append(f"\n🔍 Opération {i+1}:")
            result["differences"].extend(op_diffs)
    
    return result


def generate_comparison_report():
    """Génère un rapport de comparaison complet."""
    
    print("=" * 80)
    print("📊 COMPARAISON EXPECTED vs LLM OUTPUTS")
    print("=" * 80)
    print()
    
    expected_files = sorted(EXPECTED_DIR.glob("*.json"))
    
    total_files = len(expected_files)
    perfect_matches = 0
    files_with_errors = 0
    missing_files = 0
    false_positives = 0
    false_negatives = 0
    
    all_differences = {}
    all_false_positive_ops = []
    
    for expected_file in expected_files:
        llm_file = LLM_OUTPUT_DIR / expected_file.name
        
        result = compare_files(expected_file, llm_file)
        
        if result["status"] == "missing":
            print(result["message"])
            missing_files += 1
        elif result["status"] == "ok":
            print(f"✅ {expected_file.name}: PARFAIT ({result['expected_count']} opérations)")
            perfect_matches += 1
        elif result["status"] == "false_positive":
            print(f"🚨 {expected_file.name}: FAUX POSITIFS")
            for diff in result["differences"]:
                print(diff)
            print()
            false_positives += 1
            all_differences[expected_file.name] = result["differences"]
            all_false_positive_ops.extend(result["false_positives"])
        elif result["status"] == "false_negative":
            print(f"🚨 {expected_file.name}: FAUX NÉGATIFS")
            for diff in result["differences"]:
                print(diff)
            print()
            false_negatives += 1
            all_differences[expected_file.name] = result["differences"]
        else:
            print(f"❌ {expected_file.name}: DIFFÉRENCES TROUVÉES")
            for diff in result["differences"]:
                print(diff)
            print()
            files_with_errors += 1
            all_differences[expected_file.name] = result["differences"]
    
    # Résumé
    print()
    print("=" * 80)
    print("📈 RÉSUMÉ")
    print("=" * 80)
    print(f"Total fichiers:               {total_files}")
    print(f"✅ Correspondances parfaites:    {perfect_matches}")
    print(f"🚨 Faux positifs (ops à tort):   {false_positives}")
    print(f"🚨 Faux négatifs (ops manquées): {false_negatives}")
    print(f"❌ Autres erreurs:                {files_with_errors}")
    print(f"⚠️  Fichiers manquants:           {missing_files}")
    print()
    
    # Analyse des faux positifs
    if all_false_positive_ops:
        print("=" * 80)
        print("🔍 ANALYSE DES FAUX POSITIFS")
        print("=" * 80)
        print()
        print(f"Total d'opérations générées à tort: {len(all_false_positive_ops)}")
        print()
        
        # Patterns des faux positifs
        op_types = {}
        source_articles = {}
        
        for op in all_false_positive_ops:
            op_type = op.get("operation_type")
            op_types[op_type] = op_types.get(op_type, 0) + 1
            
            source = op.get("source_article")
            if source:
                source_articles[source] = source_articles.get(source, 0) + 1
        
        print("Types d'opérations générées à tort:")
        for op_type, count in sorted(op_types.items(), key=lambda x: -x[1]):
            print(f"  - {op_type}: {count}")
        print()
        
        if source_articles:
            print("Articles sources fréquents dans les faux positifs:")
            for article, count in sorted(source_articles.items(), key=lambda x: -x[1])[:10]:
                print(f"  - {article}: {count} fois")
            print()
    
    # Analyse des patterns d'erreurs
    if all_differences:
        print("=" * 80)
        print("🔍 ANALYSE DES PATTERNS D'ERREURS (AUTRES QUE FAUX POSITIFS/NÉGATIFS)")
        print("=" * 80)
        print()
        
        error_types = {}
        for filename, diffs in all_differences.items():
            # Exclure les faux positifs de cette analyse
            if "FAUX POSITIFS" in str(diffs) or "FAUX NÉGATIFS" in str(diffs):
                continue
            
            for diff in diffs:
                if "source_article" in diff:
                    error_types.setdefault("source_article", []).append(filename)
                if "sub_target" in diff:
                    error_types.setdefault("sub_target", []).append(filename)
                if "target_article" in diff:
                    error_types.setdefault("target_article", []).append(filename)
                if "new_content" in diff:
                    error_types.setdefault("new_content", []).append(filename)
        
        for error_type, files in error_types.items():
            print(f"🔸 {error_type}: {len(set(files))} fichiers concernés")
            for f in set(files):
                print(f"   - {f}")
        print()
    
    # Recommandations
    if files_with_errors > 0 or false_positives > 0 or false_negatives > 0:
        print("=" * 80)
        print("💡 RECOMMANDATIONS POUR AMÉLIORER LE PROMPT")
        print("=" * 80)
        print()
        
        if false_positives > 0:
            print(f"⚠️  PRIORITÉ 1 - Faux positifs: {false_positives} fichiers")
            print("   Le LLM génère des opérations alors qu'il ne devrait pas.")
            print("   Recommandations:")
            print("   - Ajouter dans le prompt: 'Si le bloc ne contient AUCUNE modification")
            print("     d'un arrêté existant, retourner une liste vide []'")
            print("   - Préciser: 'Un simple texte descriptif ou informatif sans modification")
            print("     réglementaire ne doit PAS générer d'opération'")
            print("   - Clarifier la différence entre 'texte descriptif' et 'modification réglementaire'")
            print()
        
        if false_negatives > 0:
            print(f"⚠️  Faux négatifs: {false_negatives} fichiers")
            print("   Le LLM rate des opérations qui existent.")
            print("   Recommandations:")
            print("   - Vérifier que toutes les formes de modifications sont bien décrites")
            print("   - Ajouter plus d'exemples dans le prompt")
            print()
        
        if "source_article" in error_types:
            print("🎯 source_article:")
            print("   - Le LLM ne détecte pas toujours APPENDIX")
            print("   - Ajouter dans le prompt: 'Si l'opération provient d'une annexe (balise <footer data-spec=\"appendix\">), mettre source_article = \"APPENDIX\"'")
            print()
        
        if "sub_target" in error_types:
            print("🎯 sub_target:")
            print("   - Le LLM met null au lieu de ALL/END")
            print("   - Clarifier dans le prompt: 'sub_target peut être \"ALL\" (remplacer tout l'article), \"END\" (ajouter à la fin), ou null (précision via markers)'")
            print()


if __name__ == "__main__":
    generate_comparison_report()
