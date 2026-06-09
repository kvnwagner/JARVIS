# auth_tasks.py
from google_auth_oauthlib.flow import InstalledAppFlow
import json

flow = InstalledAppFlow.from_client_secrets_file(
    'credentials.json',
    scopes=['https://www.googleapis.com/auth/tasks']
)
creds = flow.run_local_server(port=0)

with open('token_tasks.json', 'w') as f:
    f.write(creds.to_json())

print("Token guardado en token_tasks.json")