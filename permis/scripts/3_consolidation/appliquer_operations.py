# TODO: lire l'état initial (liste  structurée d'articles) et le graphe d'operations mapped
# TODO: parcourir chaque opération dans l'ordre et appliquer selon type:
#       - REPLACE / MODIFY : remplacer tout l'article ou une partie ciblée
#       - DELETE / ABROGATION : marquer status='abroge' ou retirer partie ciblée
#       - ADD : insérer nouvel article; appliquer règle simple de numérotation (ex: "bis")
# TODO: pour chaque application, ajouter une entrée dans article["trace"]
# TODO: si cible introuvable -> marquer l'opération "a_revoir" et attacher contexte. OU ALORS, au bon endroit, ajouter la modification. à l'arrache.
# TODO: sortie intermédiaire
#TODO: quand on décale la numérotation (par ex ajout ou abrogation) alors il faut mettre à jour les références des articles suivants.

def run():
    print("TODO: appliquer les opérations nettoyées sur la base d'articles (consigne de traçabilité)")

if __name__ == "__main__":
    run()