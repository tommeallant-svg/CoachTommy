from garminconnect import Garmin


class GarminClient:

    def __init__(self, email, password):
        self.client = Garmin(email, password)

    def login(self):
        self.client.login()
        return self.client