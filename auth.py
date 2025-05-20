from __future__ import print_function
import os
from datetime import datetime, timedelta, timezone as tzn
from cryptography.fernet import Fernet
from creds import *
from database import user_collection, tokens_collection, email_collection, add_user_whitelist_status, check_user_active_email, update_user_whitelist_status, update_send_whitelisted_message_status
from helpers import extract_phone_number, extract_emails, send_whatsapp_message
import secrets
from keywords import *
from text import connect_to_calendar, connect_to_calendar_confirmation

def encrypt_token(token_str):
    FERNET_KEY = os.environ["FERNET_KEY"]
    fernet = Fernet(FERNET_KEY)
    return fernet.encrypt(token_str.encode()).decode()

def decrypt_token(token_str_encrypted):
    FERNET_KEY = os.environ["FERNET_KEY"]
    fernet = Fernet(FERNET_KEY)
    return fernet.decrypt(token_str_encrypted.encode()).decode()

def save_token(user_id, creds, credentials):
    client_id = credentials["web"]["client_id"] if credentials else CLIENT_ID
    client_secret = credentials["web"]["client_secret"] if credentials else CLIENT_SECRET

    tokens_collection.update_one(
        {"user_id": user_id},
        {"$set": {
            "access_token": encrypt_token(creds.token),
            "refresh_token": encrypt_token(creds.refresh_token),
            "scopes": ",".join(SCOPES),
            "expiry": creds.expiry.isoformat(),
            "is_using_test_account": False,
            "client_id": client_id,
            "client_secret": client_secret,
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
    expires = datetime.now() + timedelta(hours=24)

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

def authenticate_command(incoming_msg, resp, user_id):
    authenticate_args = incoming_msg.split(authenticate_keyword)
    
    if len(authenticate_args) > 1: # if authenticate <email>
        user_email = extract_emails(authenticate_args)
        if user_email:
            try:
                is_whitelisted = check_user_active_email(user_id, user_email)
                if not is_whitelisted:
                    add_user_whitelist_status(user_id, user_email)
                    send_whatsapp_message(ADMIN_NUMBER, "New user request for whitelisting: " + user_email + "\n" + "link to whitelist: " + WHITELIST_LINK)
                    resp.message("⏳ Your email is now processed for whitelisting. You will receive a confirmation message within 24hr or less once it's added to the whitelist.")
                    return str(resp)
                else:
                    auth_link = generate_auth_link(user_id)
                    resp.message(f"❌ This email is already whitelisted. Click to connect your Google Calendar:\n\n{auth_link}.\n\n Select your email, then click _continue_ to connect to your account.")
                    return str(resp)
            except Exception as e:
                print(f"########### Error adding user whitelist status: {e}", flush=True)
                resp.message("❌ Error adding your email to the whitelist. Please try again.")
                send_whatsapp_message(ADMIN_NUMBER, f"ERROR: {user_id, user_email, incoming_msg, e}")
                return str(resp)
        else:
            resp.message("Unable to detect email address. Please try again.")
            send_whatsapp_message(ADMIN_NUMBER, f"ERROR: {user_id, user_email, incoming_msg, e}")
            return str(resp)

def authenticate_only_command(resp, user_id):
    print(f"########### Authenticate only command for user: {user_id}", flush=True)
    has_active_email = check_user_active_email(user_id)
    print(f"########### User {user_id} has active email: {has_active_email}", flush=True)
    if has_active_email:
        auth_link = generate_auth_link(user_id)
        resp.message(connect_to_calendar(auth_link, has_active_email))
        return str(resp)
    elif has_active_email == False:
        resp.message("❌ Your email is not yet whitelisted. Please type 'authenticate <your-google-calendar-email>' to whitelist your email")
        return str(resp)
    else:
        resp.message("Your email is pending for whitelisting. We will get back to you in 24h or less. For any questions, reach out to admin at galuh.adika@gmail.com.")
        return str(resp)

def whitelist_admin_command(incoming_msg, resp, user_id):
    if user_id == extract_phone_number(ADMIN_NUMBER):
        message_array = incoming_msg.split(" ")
        if len(message_array) > 1:
            if message_array[1] == "failed" or message_array[1] == "fail":
                email = message_array[2]
                user_number = user_collection.find_one({"email": email}).get("user_id")
                if user_number:
                        try:
                            whatsapp_number = f"whatsapp:{user_number}"
                            instruction_text = f"Your email {email} is not associated with a valid Google account, or has disabled access to 3rd-party Oauth.\n\n Please use another email address: type _authenticate <email-address>_, or contact admin for further assistance."
                            send_whatsapp_message(whatsapp_number, instruction_text)
                            send_whatsapp_message(ADMIN_NUMBER, f"email {email} has been rejected and user {user_number} has been notified.")
                            return str(resp)
                        except Exception as e:
                            print(f"########### Error sending whitelisted failed message: {str(e)}", flush=True)
                            return str(e)
            else: 
                email = message_array[1]
                user_number = update_user_whitelist_status(email, True)
                if user_number:
                    try:
                        whatsapp_number = f"whatsapp:{user_number}"
                        auth_link = generate_auth_link(user_number)
                        instruction_text = connect_to_calendar_confirmation(auth_link, email)
                        send_whatsapp_message(whatsapp_number, instruction_text)
                        send_whatsapp_message(ADMIN_NUMBER, f"email {email} has been whitelisted and user {user_number} has been notified.")
                        update_send_whitelisted_message_status(user_number)
                        return str(resp)
                    except Exception as e:
                        print(f"########### Error sending whitelisted success message: {str(e)}", flush=True)
                        return str(e)  
        else:
            resp.message("Incomplete command")
            return str(resp)