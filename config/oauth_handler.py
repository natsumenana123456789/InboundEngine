import json
import os
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

class OAuthHandler:
    def __init__(self):
        self.credentials_path = os.path.join(os.path.dirname(__file__), 'oauth_credentials.json')
        self.token_path = os.path.join(os.path.dirname(__file__), 'token.json')

    def get_credentials(self):
        creds = None
        if os.path.exists(self.token_path):
            creds = Credentials.from_authorized_user_file(self.token_path, SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_path, SCOPES)
                creds = flow.run_local_server(port=8080)

            with open(self.token_path, 'w') as token:
                token.write(creds.to_json())

        return creds

    def revoke_credentials(self):
        if os.path.exists(self.token_path):
            os.remove(self.token_path) 