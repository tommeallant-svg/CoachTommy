import json
from garminconnect import Garmin


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
        print(self)
        
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
            print("try garmin email password")
            self.client = Garmin(email, password)
            self.is_authenticated = False
        else:
            raise ValueError("Either email/password or token_dict must be provided")

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
            self.client.login()
            self.is_authenticated = True
            self.email = self.client.username
            return self.get_token_dict()

        except Exception as e:
            # Si le login via token échoue (ex: expiré), on marque comme non authentifié
            print(f"Garmin token login with password failed: {e}")
            self.is_authenticated = False
            return 0
        
    def get_token_dict(self):
        """
        Retourne les tokens d'accès sous forme de dictionnaire.
        """
        if not hasattr(self.client, 'login_token_store') or not self.client.login_token_store:
            return None
            
        return self.client.login_token_store

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
