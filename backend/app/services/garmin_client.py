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
        if token_dict:
            # Si on a des tokens, initialiser avec eux
            self.client = Garmin()
            self.client.login_token_store = token_dict
            self.client.session = self._create_session_from_token(token_dict)
            self.is_authenticated = True
        elif email and password:
            # Sinon, créer un nouveau client avec email/password
            self.client = Garmin(email, password)
            self.is_authenticated = False
        else:
            raise ValueError("Either email/password or token_dict must be provided")
        
        self.email = email
        self._token_dict = token_dict

    def _create_session_from_token(self, token_dict):
        """Crée une session requests avec le token."""
        import requests
        session = requests.Session()
        session.headers.update({
            "Authorization": f"{token_dict.get('token_type', 'Bearer')} {token_dict.get('access_token')}",
            "NK": "NT"
        })
        return session

    def login(self):
        """
        Se connecte à Garmin Connect avec email/password.
        Retourne les tokens d'accès.
        """
        if self.is_authenticated:
            return self.get_token_dict()
            
        self.client.login()
        self.is_authenticated = True
        self.email = self.client.client_email
        return self.get_token_dict()

    def get_token_dict(self):
        """
        Retourne les tokens d'accès sous forme de dictionnaire.
        """
        if not hasattr(self.client, 'login_token_store') or not self.client.login_token_store:
            return None
            
        token_store = self.client.login_token_store
        return {
            "access_token": token_store.get("access_token"),
            "refresh_token": token_store.get("refresh_token"),
            "token_type": token_store.get("token_type"),
            "expires_in": token_store.get("expires_in")
        }

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