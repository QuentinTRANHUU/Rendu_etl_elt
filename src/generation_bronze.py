import ollama
import json
import os
import itertools
import pandas as pd
from tqdm import tqdm
from datetime import datetime
from dotenv import load_dotenv
import subprocess
import time
import requests

# Chargement et configuration via le .env
load_dotenv()  # Charge les variables du fichier .env situé à la racine

# Récupération des paramètres de simulation
NB_TOURS = int(os.getenv("NB_TOURS_PAR_PARTIE", 5))
DUREE_MEMOIRE = int(os.getenv("DUREE_MEMOIRE_AGENTS", 5))

# Récupération des paramètres LLM
MODELE_ENV = os.getenv("MODELE_LLM", "llama3:8b")
TEMPERATURE_LLM = float(os.getenv("LLM_TEMPERATURE", 0.3))

# Récupération des chemins de fichiers
CHEMIN_PROMPTS = os.getenv("CHEMIN_PROMPTS_JSON", r"data\prompts_regles_et_profils.json")
DOSSIER_SORTIE = os.getenv("CHEMIN_DOSSIER_DATA", "data") + "/bronze"

# Récupération de la matrice des gains
# Définition de la matrice de gains par défaut
MATRICE_GAINS_DEFAULT = {
    "COOPERER,COOPERER":[3,3],
    "COOPERER,TRAHIR":[0,5],
    "TRAHIR,COOPERER":[5,0],
    "TRAHIR,TRAHIR":[1,1]
    }
raw_matrix = json.loads(os.getenv("MATRICE_GAINS",MATRICE_GAINS_DEFAULT))
MATRICE_GAINS = {tuple(k.split(",")): tuple(v) for k, v in raw_matrix.items()}

# Chargement dynamique du fichier JSON des prompts
with open(CHEMIN_PROMPTS, encoding="utf-8") as f:
    PROMPTS_CONFIG = json.load(f)

def obtenir_decision_llm(nom_profil, texte_historique_contexte):
    """
    Interroge Ollama en assemblant les règles globales, le profil de l'agent,
    l'historique croisé et les contraintes de formatage JSON issues du fichier externe.
    """
    regles = PROMPTS_CONFIG["Regles_du_jeu"]
    personnalite = PROMPTS_CONFIG[nom_profil]
    format_reponse = PROMPTS_CONFIG["Format_reponse"]
    
    # Assemblage complet et propre du System Prompt
    profil_system = (
        f"{regles}\n\n"
        f"Ton profil psychologique pour cette partie :\n{personnalite}\n\n"
        f"{format_reponse}"
    )
    
    # Prompt utilisateur contenant l'historique complet (choix + intentions)
    contexte_jeu = (
        f"{texte_historique_contexte}\n"
        "C'est le moment de jouer le prochain tour. Quelle est ta décision ?"
    )
    
    response = ollama.chat(
        model=MODELE_ENV,
        messages=[
            {'role': 'system', 'content': profil_system},
            {'role': 'user', 'content': contexte_jeu}
        ],
        options={'temperature': TEMPERATURE_LLM}
    )
    
    try:
        contenu = response['message']['content']
        start = contenu.find('{')
        end = contenu.rfind('}') + 1
        json_str = contenu[start:end]
        
        data = json.loads(json_str)
        
        # 1. Sécurité indispensable : on force toutes les clés générées par le LLM en minuscules
        data_clean = {k.lower(): v for k, v in data.items()}
        
        # 2. Récupération et nettoyage du choix
        choix = str(data_clean.get("choix", "COOPERER")).upper().strip()
        if choix not in ["COOPERER", "TRAHIR"]:
            choix = "COOPERER"
            
        # 3. Récupération sécurisée avec des phrases de repli explicites (évite le None)
        # Si le LLM se trompe de clé, on cherche d'abord la bonne version, sinon on prend une valeur par défaut
        justif_prive = data_clean.get("justification_prive", "Aucune réflexion privée enregistrée par l'IA.")
        justif_public = data_clean.get("justification_public", "Aucune déclaration publique enregistrée par l'IA.")
        
        return choix, justif_prive, justif_public

    except Exception as e:
        # En cas de plantage total du décodage JSON, on évite le crash du tournoi avec des valeurs propres
        return "COOPERER", f"Erreur de parsing privé (Détail: {str(e)})", f"Erreur de parsing public (Détail: {str(e)})"

def construire_contexte_historique(tours_passes, pour_joueur_numero):
    """
    Génère un récapitulatif textuel des "duree_memoire" derniers tours adapté à la perspective de l'agent.
    Inclut les choix ET les justifications des deux côtés.
    """
    if not tours_passes:
        return "C'est le premier tour de la partie. Aucun historique disponible. Fais ton premier choix."
    
    contexte = "Voici le contexte et l'historique des derniers tours de cette partie :\n"
    
    # Limite aux "duree_memoire" derniers tours pour optimiser la fenêtre de contexte
    for t in tours_passes[-DUREE_MEMOIRE:]:
        if pour_joueur_numero == 1:
            mon_choix = t["joueur_1_choix"]
            ma_justif_public = t["joueur_1_justification_public"]
            ma_justif_prive = t["joueur_1_justification_prive"]
            son_choix = t["joueur_2_choix"]
            sa_justif_public = t["joueur_2_justification_public"]
        else:
            mon_choix = t["joueur_2_choix"]
            ma_justif_public = t["joueur_2_justification_public"]
            ma_justif_prive = t["joueur_2_justification_prive"]
            son_choix = t["joueur_1_choix"]
            sa_justif_public = t["joueur_1_justification_public"]
            
        contexte += (
            f"- Tour {t['tour']} :\n"
            f"  * Tu as choisi '{mon_choix}'."
            f"  * Ta justification publique était : \"{ma_justif_public}\"\n"
            f"  * Ta justification privée était : \"{ma_justif_prive}\"\n"
            f"  * Ton adversaire a choisi '{son_choix}'. Sa justification publique était : \"{sa_justif_public}\"\n"
        )
    
    contexte += "\nEn analysant comment l'adversaire réagit à tes choix et justifications,"
    contexte += " prends ta décision pour le tour actuel en accord avec ton profil."
    return contexte

def simuler_partie(agent_1_nom, agent_2_nom):
    tours_data = []
    score_cumule_1 = 0
    score_cumule_2 = 0

    for tour in range(1, NB_TOURS + 1):
        # 1. Génération de l'historique croisé (Choix + Raisonnements)
        contexte_j1 = construire_contexte_historique(tours_data, pour_joueur_numero=1)
        contexte_j2 = construire_contexte_historique(tours_data, pour_joueur_numero=2)
        
        # 2. Interrogation des agents IA
        choix_1, justif_prive_1, justif_public_1 = obtenir_decision_llm(agent_1_nom, contexte_j1)
        choix_2, justif_prive_2,justif_public_2 = obtenir_decision_llm( agent_2_nom, contexte_j2)
        
        # 3. Calcul des scores
        gain_1, gain_2 = MATRICE_GAINS[(choix_1, choix_2)]
        score_cumule_1 += gain_1
        score_cumule_2 += gain_2
        
        # 4. Enregistrement dans la structure de données
        tour_info = {
            "tour": tour,
            "joueur_1_profil": agent_1_nom,
            "joueur_2_profil": agent_2_nom,
            "joueur_1_choix": choix_1,
            "joueur_2_choix": choix_2,
            "joueur_1_gain": gain_1,
            "joueur_2_gain": gain_2,
            "joueur_1_score_cumule": score_cumule_1,
            "joueur_2_score_cumule": score_cumule_2,
            "joueur_1_justification_prive": justif_prive_1,
            "joueur_2_justification_prive": justif_prive_2,
            "joueur_1_justification_public": justif_public_1,
            "joueur_2_justification_public": justif_public_2
        }
        tours_data.append(tour_info)
        
    return tours_data

def executer_tournoi(liste_profils):
    """
    [NOUVEAU] Fait s'affronter tous les profils deux à deux avec des paramètres fixes.
    Ajoute les colonnes de métadonnées globales de configuration à chaque ligne.
    """
    try:
        print(f"Modèle utilisé : {MODELE_ENV}")

        tous_les_tours_tournoi = []
        
        # Génère toutes les paires uniques possibles (inclut un profil contre lui-même)
        matchs = list(itertools.combinations_with_replacement(liste_profils, 2))
        
        for index, (agent_1, agent_2) in tqdm(enumerate(matchs)):
            print(f"Lancement : {agent_1} VS {agent_2} ({NB_TOURS} tours)...")
            
            tours_partie = simuler_partie(agent_1, agent_2)
            
            # Injection des colonnes de métadonnées globales demandées
            for tour in tours_partie:
                tour["param_duree_memoire"] = DUREE_MEMOIRE
                tour["param_total_tours_partie"] = NB_TOURS
                tour["param_matrice_gains"] = "standard_axelrod"
                
            tous_les_tours_tournoi.extend(tours_partie)
            
        # Structuration et sauvegarde Parquet (Couche Bronze)
        df_tournoi = pd.DataFrame(tous_les_tours_tournoi)

        # Création du dossier complet (ex: data/bronze) pour éviter le FileNotFoundError
        os.makedirs(DOSSIER_SORTIE, exist_ok=True)

        horodatage = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Nettoyage sécurisé du nom du modèle
        modele_propre = (
            MODELE_ENV.replace(":", "_")
            .replace(" ", "_")
            .replace("\\", "_")
            .replace("/", "_")
            .replace(".", "_")
            .replace("@", "_")
        )

        # CORRECTION 3 : Utilisation de os.path.join pour éviter les conflits de Slashes/Antislashes
        nom_fichier_parquet = os.path.join(
            DOSSIER_SORTIE,
            f"simulation_tournoi_{modele_propre}_{NB_TOURS}_tours_{DUREE_MEMOIRE}_memoire_{horodatage}.parquet"
        )

        df_tournoi.to_parquet(nom_fichier_parquet, index=False)

        print(f"\nTournoi terminé ! {len(df_tournoi)} lignes enregistrées dans '{nom_fichier_parquet}'.")

    except Exception as e:
        # Valeur de secours si Ollama n'est pas lancé ou est vide
        print(f"Erreur critique durant le tournoi : {str(e)}")

# Extraction automatique des profils disponibles dans le JSON (en ignorant les clés de config)
PROFILS_AGENTS = [cle for cle in PROMPTS_CONFIG.keys() if cle not in ["Regles_du_jeu", "Format_reponse"]]

# On vérifie qu'Ollama est bien lancé, on le lance (et on fait les éventuels téléchargements) au besoin
def init_ollama_environment(model_name=MODELE_ENV):
    """
    Vérifie Ollama et le démarre si nécessaire, puis s'assure que le modèle est présent.
    RETOURNE : Le processus Popen si démarré par le script, sinon None.
    """
    print("[Ollama] Vérification du serveur...")
    ollama_url = "http://localhost:11434/"
    ollama_process = None
    server_active = False
    
    # 1. On teste si le serveur est déjà actif
    try:
        response = requests.get(ollama_url, timeout=3)
        if response.status_code == 200:
            print("[Ollama] Le serveur est déjà actif.")
            server_active = True
    except requests.exceptions.RequestException:
        pass

    # 2. Si non détecté, on tente de le démarrer
    if not server_active:
        print("[Ollama] Serveur non détecté. Tentative de démarrage automatique...")
        try:
            ollama_process = subprocess.Popen(
                ["ollama", "serve"], 
                stdout=subprocess.DEVNULL, 
                stderr=subprocess.DEVNULL
            )
            
            for i in range(6):
                time.sleep(3)
                try:
                    requests.get(ollama_url, timeout=5)
                    print("[Ollama] Le serveur a démarré avec succès.")
                    server_active = True
                    break
                except requests.exceptions.RequestException:
                    if i == 5:
                        raise RuntimeError("Impossible de joindre Ollama après lancement automatique.")
        except FileNotFoundError:
            raise FileNotFoundError("La commande 'ollama' est introuvable sur ce système.")

    # 3. Vérification obligatoire du modèle (exécutée TOUT LE TEMPS maintenant)
    print(f"[Ollama] Vérification du modèle '{model_name}'...")
    try:
        check_model = requests.post(f"{ollama_url}api/show", json={"name": model_name})
        if check_model.status_code != 200:
            print(f"[Ollama] Téléchargement de '{model_name}' (cela peut prendre quelques minutes)...")
            subprocess.run(["ollama", "pull", model_name], check=True)
            print(f"[Ollama] Modèle '{model_name}' téléchargé avec succès.")
        else:
            print(f"[Ollama] Modèle '{model_name}' déjà disponible en local.")
    except Exception as e:
        print(f"Impossible de vérifier ou télécharger le modèle : {e}")
        
    return ollama_process


def stop_ollama_environment(ollama_process):
    """
    Arrête proprement le processus Ollama s'il a été initié par ce script.
    """
    if ollama_process:
        print("[Ollama] Arrêt du serveur Ollama initié par le script pour libérer la RAM...")
        ollama_process.terminate()  # Demande une fermeture propre
        try:
            ollama_process.wait(timeout=5)
            print("[Ollama] Serveur arrêté et mémoire libérée.")
        except subprocess.TimeoutExpired:
            ollama_process.kill()  # Force l'arrêt si ça bloque
            print("[Ollama] Serveur tué de force (timeout dépassé).")
    else:
        print("[Ollama] Le serveur tournait avant le script, il est laissé actif.")

# Exécution du tournoi à la place d'une partie de test unique
if __name__ == "__main__":

    ollama_proc = init_ollama_environment()

    try :
        executer_tournoi(PROFILS_AGENTS)
    finally :
        stop_ollama_environment(ollama_proc)