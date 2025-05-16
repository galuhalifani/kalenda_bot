from __future__ import print_function
import os
from datetime import datetime, timedelta, timezone as tzn
from cryptography.fernet import Fernet
from creds import *
from database import user_collection, tokens_collection
from helpers import extract_phone_number
import secrets

def encrypt_token(token_str):
    FERNET_KEY = os.environ["FERNET_KEY"]
    fernet = Fernet(FERNET_KEY)
    return fernet.encrypt(token_str.encode()).decode()

def decrypt_token(token_str_encrypted):
    FERNET_KEY = os.environ["FERNET_KEY"]
    fernet = Fernet(FERNET_KEY)
    return fernet.decrypt(token_str_encrypted.encode()).decode()

def save_token(user_id, creds):
    tokens_collection.update_one(
        {"user_id": user_id},
        {"$set": {
            "access_token": encrypt_token(creds.token),
            "refresh_token": encrypt_token(creds.refresh_token),
            "scopes": ",".join(SCOPES),
            "expiry": creds.expiry.isoformat(),
            "is_using_test_account": False
        }},
    upsert=True)

    user_collection.update_one(
        {"user_id": user_id},
        {"$set": {
            "is_using_test_account": False
        }},
    upsert=True)

def generate_auth_link(user_id):
    token = secrets.token_hex(16)
    print(f"########### Generated token: {token}", flush=True)
    expires = datetime.now() + timedelta(minutes=30)

    tokens_collection.update_one(
        {"user_id": user_id},
        {"$set": {
            "auth_token_link": token,
            "auth_token_link_expiry": expires.isoformat()
        }},
    upsert=True
    )

    CONNECT_URI = CONNECT_AUTH_URI if mode == 'production' else CONNECT_AUTH_URI_TEST
    return f"{CONNECT_URI}?user_id={user_id}&token={token}"

def verify_auth_token_link(user_id, token):
    print(f"########### Verifying auth token link for user: {user_id}, token: {token}", flush=True)
    record = tokens_collection.find_one({"auth_token_link": token})
    print(f"########### Record: {record}", flush=True)
    record_user_id = record.get("user_id") if record else None

    phone_number = user_id
    record_phone_number = record_user_id
    
    phone_number = extract_phone_number(user_id)
    record_phone_number = extract_phone_number(record_user_id)

    print(f"########### Record phone number: {record_phone_number}, Phone number: {phone_number}", flush=True)
    token_is_valid = record_phone_number == phone_number

    if not record or not token_is_valid:
        return "❌ Invalid link. Please try again. Type 'authenticate' to generate a new link."
    
    if datetime.now() > datetime.fromisoformat(record["auth_token_link_expiry"]):
        return "❌ Link is expired. Please try again. Type 'authenticate' to generate a new link."
    
    return "verified"

def verify_oauth_connection(user_id):
    print(f"########### Verifying OAuth connection for user: {user_id}", flush=True)
    user_token = tokens_collection.find_one({"user_id": user_id, "refresh_token": {"$exists": True}})
    if not user_token:
        return False
    
    return True