# Permis — pipeline de consolidation (version simple)

Objectif : traiter un dossier d'arrêtés (AP) pour produire un permis consolidé (HTML).
Contrainte : garder archive/ et réutiliser block_splitter.py, extract_new_content.py, ask_llm.py.

Ordre minimal des étapes :
1) Préparer et classer les arrêtés (nettoyage + classification)
2) Découper en blocs et détecter les opérations (LLM)
3) Nettoyer les opérations et extraire le contenu (remplacer markers)
4) Consolider les articles (appliquer opérations)
5) Générer sorties (HTML, rapport)

Voir scripts/* pour les fichiers et les TODOs.




TODO globaux 
TODO plus tard: adapter tous les fichiers pour ne remplir le bon numéro d'icpe une seule fois. 