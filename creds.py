from __future__ import print_function
import os
from dotenv import load_dotenv

load_dotenv(override=True)
mode = os.getenv("MODE")
MONGODB_URL=os.getenv('MONGO_URI')
OPENAI_KEY=os.getenv('OPENAI_API_KEY')
CLIENT_ID = os.environ["GOOGLE_CLIENT_ID"]
CLIENT_SECRET = os.environ["GOOGLE_CLIENT_SECRET"]
CLIENT_ID_PRIMARY = os.environ["GOOGLE_CLIENT_ID_PRIMARY"]
CLIENT_SECRET_PRIMARY = os.environ["GOOGLE_CLIENT_SECRET_PRIMARY"]
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
TWILIO_PHONE_NUMBER_TEST = os.environ.get("TWILIO_PHONE_NUMBER_TEST")
WHITELIST_KEYWORD = os.environ.get("WHITELIST_KEYWORD")
ADMIN_NUMBER = os.environ.get("ADMIN_NUMBER")
WHITELIST_LINK = os.environ.get("WHITELIST_LINK")


def get_credentials(client_type):
    if client_type == 'primary':
        return {
            "web": {
                "client_id": CLIENT_ID_PRIMARY,
                "client_secret": CLIENT_SECRET_PRIMARY,
                "redirect_uris": [REDIRECT_URI],
                "auth_uri": AUTH_URI,
                "token_uri": TOKEN_URI
            }
        }
    else:
        return {
            "web": {
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "redirect_uris": [REDIRECT_URI],
                "auth_uri": AUTH_URI,
                "token_uri": TOKEN_URI
            }
        }
