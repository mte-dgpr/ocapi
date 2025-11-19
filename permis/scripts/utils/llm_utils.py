

def call_llm_api(prompt: str) -> dict:
    """
    Fonction fictive pour simuler un appel à une API de LLM.
    Remplacer par l'implémentation réelle.
    """
    # Simuler une réponse
    response = {
        "type": "FULL_SECTION",
        "position": None,
        "details": {}
    }
    return response

def query_llm_for_subtarget(text: str, context_html: str) -> dict:
    """
    Interroge un LLM pour déterminer le sub-target à partir d'un texte descriptif et d'un contexte HTML.
    Retourne un dictionnaire avec les informations du sub-target.
    (REPLACE)
    """
    prompt_REPLACE = f"""
    Vous êtes un assistant spécialisé dans l'analyse juridique. Dans le texte suivant : 
    
    {target_content}
    
    Supprime le contenu décrit de la manière suivante : 
    
    {sub_target}
    
    et remplace le par le placeholder <NEWCONTENT>.
    """

    prompt_ADD = f"""
    Vous êtes un assistant spécialisé dans l'analyse juridique. Dans le texte suivant : 
    
    {target_content}
    
    A l'endroit décrit de la manière suivante : 
    
    {sub_target}
    
    insère le placeholder <NEWCONTENT>.
    """

    prompt_REMOVE = f"""
    Vous êtes un assistant spécialisé dans l'analyse juridique. Dans le texte suivant : 
    
    {target_content}
    
    Supprime le segment décrit de la manière suivante : 
    
    {sub_target}
    """

    # TODO : Si introuvable, répondre introuvable. 

    # Appel au LLM (fonction fictive, à remplacer par l'appel réel)
    response = call_llm_api(prompt)

    return response