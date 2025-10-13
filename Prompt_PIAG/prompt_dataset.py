import json
import requests
import time
import re
from pathlib import Path
from sklearn.metrics import classification_report

API_URL = "https://preprod.api.piag.e2.rie.gouv.fr/v1/chat/completions"
API_KEY = ""
MODEL_NAME = "mte-api-piag-mistral-small-latest"

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}


def ask_llm_for_operation(text_block):
    prompt = f"""
Voici un extrait de texte juridique :

\"{text_block}\"

Ta tâche est de détecter si ce texte contient une opération juridique de type modification, ajout ou abrogation. Si oui, retourne un JSON structuré dans ce format :

{{
  "is_modification": true,
  "modification_type": "ADD|REPLACE|REMOVE",
  "target": "article ou élément concerné",
  "operand": "contenu ajouté, supprimé ou modifié"
}}

Sinon, retourne simplement :

{{ "is_modification": false }}
"""
    data = {
        "model": MODEL_NAME,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.0
    }

    try:
        response = requests.post(API_URL, headers=HEADERS, json=data)
        response.raise_for_status()
        raw_content = response.json()["choices"][0]["message"]["content"]
        match = re.search(r"\{[\s\S]*\}", raw_content)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                return {"is_modification": False}
        return {"is_modification": False}

    except Exception as e:
        print("❌ Erreur API ou parsing JSON :", e)
        return {"is_modification": False}


def evaluate_mistral_on_labeled_dataset(test_file: Path, save_output: Path = None):
    """Évalue Mistral sur un jeu labellisé """
    with open(test_file, "r", encoding="utf-8") as f:
        dataset = json.load(f)

    y_true = []
    y_pred = []
    raw_results = []

    for idx, item in enumerate(dataset):
        text = item.get("text", "")
        label = item.get("label", 0)  # 0 = AUTRE, 1 = MODIF
        y_true.append(label)

        print(f"[{idx+1}/{len(dataset)}] Traitement : {text[:60]}...")
        response = ask_llm_for_operation(text)
        pred_label = int(response.get("is_modification", False))
        y_pred.append(pred_label)

        raw_results.append({
            "text": text,
            "true_label": label,
            "predicted_label": pred_label,
            "raw_response": response
        })

        time.sleep(3)  # API rate limit

    print("\n Rapport de classification :")
    print(classification_report(y_true, y_pred, target_names=["AUTRE", "MODIF"]))

    if save_output:
        with open(save_output, "w", encoding="utf-8") as f:
            json.dump(raw_results, f, ensure_ascii=False, indent=2)
        print(f"\n Résultats détaillés sauvegardés dans : {save_output}")


if __name__ == "__main__":
    test_path = Path(r"C:\Users\thanina.ait-ferhat\Desktop\Test\test.json")
    output_path = Path(r"C:\Users\thanina.ait-ferhat\Desktop\Test\resultats_mistral.json")

    evaluate_mistral_on_labeled_dataset(test_path, save_output=output_path)
