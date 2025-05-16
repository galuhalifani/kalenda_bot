from __future__ import print_function
import os
from dotenv import load_dotenv

load_dotenv(override=True)
mode = os.getenv("MODE")
MONGODB_URL=os.getenv('MONGO_URI')
OPENAI_KEY=os.getenv('OPENAI_API_KEY')
CLIENT_ID = os.environ["GOOGLE_CLIENT_ID"]
CLIENT_SECRET = os.environ["GOOGLE_CLIENT_SECRET"]
TEST_CLIENT_ID = os.environ["TEST_CLIENT_ID"]
TEST_CLIENT_SECRET = os.environ["TEST_CLIENT_SECRET"]
TOKEN_URI = os.environ["TOKEN_URI"]
AUTH_URI = os.environ["AUTH_URI"]
CONNECT_AUTH_URI = os.environ["CONNECT_AUTH_URI"]
CONNECT_AUTH_URI_TEST = os.environ["CONNECT_AUTH_URI_TEST"]
REDIRECT_URI = os.environ["REDIRECT_URI"]
REDIRECT_URI_TEST = os.environ["REDIRECT_URI_TEST"]
TWILIO_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
SCOPES = [
    'https://www.googleapis.com/auth/calendar.events',
    'https://www.googleapis.com/auth/calendar.readonly'
]
TWILIO_PHONE_NUMBER = os.environ.get("TWILIO_PHONE_NUMBER")
TWILIO_PHONE_NUMBER_SANDBOX = os.environ.get("TWILIO_PHONE_NUMBER_SANDBOX")

env_credentials = {
    "MONGODB_URL": MONGODB_URL,
    "OPENAI_KEY": OPENAI_KEY,
    "CLIENT_ID": CLIENT_ID,
    "CLIENT_SECRET": CLIENT_SECRET,
    "TEST_CLIENT_ID": TEST_CLIENT_ID,
    "TEST_CLIENT_SECRET": TEST_CLIENT_SECRET,
    "TOKEN_URI": TOKEN_URI,
    "AUTH_URI": AUTH_URI,
    "CONNECT_AUTH_URI": CONNECT_AUTH_URI,
    "CONNECT_AUTH_URI_TEST": CONNECT_AUTH_URI_TEST,
    "REDIRECT_URI": REDIRECT_URI,
    "REDIRECT_URI_TEST": REDIRECT_URI_TEST,
    "TWILIO_SID": TWILIO_SID,
    "TWILIO_AUTH_TOKEN": TWILIO_AUTH_TOKEN,
    "SCOPES": SCOPES
}

def get_credentials():
    return {
        "web": {
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "redirect_uris": [REDIRECT_URI],
            "auth_uri": AUTH_URI,
            "token_uri": TOKEN_URI
        }
    }
