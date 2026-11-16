import json
import os
from garminconnect import Garmin
from pathlib import Path

class GarminClient:
    """
    Client pour interagir avec l'API Garmin Connect.
    
    Gère la connexion, la persistance des tokens et l'envoi de workouts.
    """

    def __init__(self, email: str = None, password: str = None, token_dict: dict = None):
        """
        Initialise le client Garmin.
        
        Args:
            email: Email Garmin Connect
            password: Mot de passe Garmin Connect
            token_dict: Dictionnaire contenant les tokens si déjà connecté
                      Format: {"access_token": "...", "refresh_token": "...", "token_type": "...", "expires_in": ...}
        """
        self.email = email
        self._token_dict = token_dict
        
        if token_dict:
            # Si on a des tokens, initialiser avec eux via la méthode native
            self.client = Garmin()
            try:
                # Utilisation du tokenstore en format JSON string comme supporté par la lib
                self.client.login(tokenstore=json.dumps(token_dict))
                self.is_authenticated = True
                # Récupérer l'email (username) depuis le client après login réussi par token
                self.email = self.client.username
            except Exception as e:
                # Si le login via token échoue (ex: expiré), on marque comme non authentifié
                print(f"Garmin token login failed: {e}")
                self.is_authenticated = False
        elif email and password:
            # Sinon, créer un nouveau client avec email/password
            self.client = Garmin(email, password)
            self.is_authenticated = False
        else:
            raise ValueError("Either email/password or token_dict must be provided")

    @staticmethod
    def sync_tokens_to_file(garmin_token_json: str):
        """
        Synchronise les tokens JSON vers le fichier spécifié par GARMINTOKENS.
        """
        tokenstore = os.getenv("GARMINTOKENS", "~/.garminconnect_session.json")
        tokenstore_path = Path(tokenstore).expanduser()
        
        # Si le chemin pointé est un dossier, on utilise un fichier à l'intérieur
        if tokenstore_path.is_dir():
            tokenstore_path = tokenstore_path / "session.json"
            
        tokenstore_path_str = str(tokenstore_path)
        
        if garmin_token_json:
            # Créer le répertoire parent si nécessaire
            os.makedirs(os.path.dirname(tokenstore_path_str), exist_ok=True)
            try:
                with open(tokenstore_path_str, "w") as f:
                    f.write(garmin_token_json)
            except Exception as e:
                print(f"Error writing tokens to {tokenstore_path_str}: {e}")
        else:
            # Si pas de tokens, on supprime le fichier pour éviter les conflits de session
            if tokenstore_path.exists() and tokenstore_path.is_file():
                try:
                    os.remove(tokenstore_path_str)
                except Exception:
                    pass
        return tokenstore_path_str

    def login(self):
        """
        Se connecte à Garmin Connect avec email/password.
        Retourne les tokens d'accès.
        """
        if self.is_authenticated:
            # Vérifier si on peut obtenir un token_dict valide
            tokens = self.get_token_dict()
            if tokens:
                return tokens
            
        try:
            tokenstore = os.getenv("GARMINTOKENS", "~/.garminconnect_session.json")
            tokenstore_path = Path(tokenstore).expanduser()
            
            if tokenstore_path.is_dir():
                tokenstore_path = tokenstore_path / "session.json"
                
            tokenstore_path_str = str(tokenstore_path)
            
            self.client.login(tokenstore_path_str)
            self.is_authenticated = True
            print("success login")
            print(self.client.username)
            return tokenstore_path

        except Exception as e:
            # Si le login via token échoue (ex: expiré), on marque comme non authentifié
            print(f"Garmin token login with password failed: {e}")
            self.is_authenticated = False
            return None
        
    def get_token_dict(self):
        """
        Retourne les tokens d'accès sous forme de dictionnaire.
        """
        try:
            # On utilise la méthode dumps() du client interne de garminconnect
            # qui est gérée par garth/client
            if hasattr(self.client, 'client'):
                tokens_json = self.client.client.dumps()
                return json.loads(tokens_json)
            return None
        except Exception as e:
            print(f"Error dumping tokens: {e}")
            return None

    def logout(self):
        """Se déconnecte de Garmin Connect."""
        if hasattr(self.client, 'logout'):
            self.client.logout()
        self.is_authenticated = False
        self._token_dict = None

    def upload_workout(self, workout_data: dict):
        """
        Crée un workout sur Garmin Connect.
        
        Args:
            workout_data: Données du workout au format Garmin
        """
        return self.client.upload_workout(workout_data)
