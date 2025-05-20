import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from flask import Flask, request, jsonify, redirect, session
from google_auth_oauthlib.flow import Flow
from twilio.twiml.messaging_response import MessagingResponse
from creds import *
from keywords import *
from model import summarize_event, mode
from helpers import extract_emails, extract_phone_number, get_image_data_url, send_whatsapp_message, get_voice_data_url, trim_reply
from auth import verify_auth_token_link, verify_oauth_connection, save_token, get_credentials, generate_auth_link, authenticate_command, authenticate_only_command, whitelist_admin_command
from database import check_user, check_user_balance, deduct_chat_balance, use_test_account, check_user_active_email, update_user_whitelist_status, update_send_whitelisted_message_status, add_user_whitelist_status, update_send_test_calendar_message, revoke_access_command
from text import greeting, using_test_calendar
from session_memory import delete_user_memory, add_user_memory
import secrets
from flask import request

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", secrets.token_hex(16))

@app.route("/")
def root():
    return "Kalenda Bot API is running."

@app.route("/auth")
def auth():
    try:
        user_id = request.args.get("user_id")
        token = request.args.get("token")
        verification = verify_auth_token_link(user_id, token)

        print(f"########### Auth Verification result: {verification}", flush=True)
        if verification != 'verified':
            return verification
        
        session['user_id'] = user_id
        credentials = get_credentials()
        flow = Flow.from_client_config(
            credentials,
            scopes=SCOPES,
            redirect_uri=REDIRECT_URI if mode == 'production' else REDIRECT_URI_TEST
        )
        auth_url, state = flow.authorization_url(prompt='consent')
        session["state"] = state
        return redirect(auth_url)
    except Exception as e:
        print(f"########### ERROR in auth: {e}", flush=True)
        return "❌ Error during authentication. Please try again."

@app.route("/oauthcallback")
def oauth_callback():
    print(f"########### OAuth callback triggered", flush=True)
    try:
        state = session["state"]
        user_id = session["user_id"]
        credentials = get_credentials()
        flow = Flow.from_client_config(
            credentials,
            scopes=SCOPES,
            state=state,
            redirect_uri=REDIRECT_URI if mode == 'production' else REDIRECT_URI_TEST
        )
        flow.fetch_token(authorization_response=request.url)
        creds = flow.credentials

        try:
            save_token(user_id, creds, credentials)
        except Exception as e:
            print(f"########### ERROR saving token: {e}", flush=True)
            return "❌ Error saving token. Please try again."
        
        print(f"########### User {user_id} connected to Google Calendar.", flush=True)
        return "✅ Google Calendar connected! You can now use the bot."
    except Exception as e:
        print(f"########### ERROR in oauth_callback: {e}", flush=True)
        return "❌ Error during oauth callback. Please try again."

@app.route('/webhook', methods=['POST'])
def receive_whatsapp():
    try:
        incoming_msg = request.values.get("Body", "").strip()
        lower_incoming_msg = incoming_msg.lower()
        record_user_id = request.values.get("From", "").strip()
        user_id = extract_phone_number(record_user_id)
        media_url = request.form.get("MediaUrl0")
        content_type = request.form.get("MediaContentType0") 
        is_authenticating = lower_incoming_msg.startswith(authenticate_keyword)
        is_authenticating_test = lower_incoming_msg == "authenticate test"
        is_whitelisting = lower_incoming_msg.startswith(WHITELIST_KEYWORD)
        is_revoking = lower_incoming_msg.startswith(revoke_access_keyword)
        is_audio = False
        is_image = False

        if content_type:
            is_audio = bool(media_url) and content_type.startswith("audio/")
            is_image = bool(media_url) and content_type.startswith("image/")

        resp = MessagingResponse()
        is_test = False
        
        try:
            print(f"########### Check User: {user_id}", flush=True)
            user = check_user(user_id)
            is_test = user.get("is_using_test_account", True)
            if (user['status'] == 'new'):
                print(f"########### Send initial greetings: {user_id}")
                try:
                    send_whatsapp_message(record_user_id, greeting)
                except Exception as e:
                    print(f"########### ERROR sending greeting: {e}", flush=True)

            is_balance_available = check_user_balance(user)

            if not is_balance_available:
                reply = "Sorry, you have reached your daily conversation limit. You can start a new conversation tomorrow."
                resp.message(reply)
                return str(resp)
        except Exception as e:
            print(f"########### ERROR initial checkings: {e}", flush=True)

        try:
            print(f"########### Check Authenticate Keyword: {incoming_msg}", flush=True)
            if is_authenticating:
                print(f"########### Check Authenticate Email Keyword: {incoming_msg}", flush=True)
                authenticate_args = incoming_msg.split(authenticate_keyword)
                
                if len(authenticate_args) > 1: # if authenticate <email>
                    return authenticate_command(incoming_msg, resp, user_id)

                # if just authenticate
                print(f"########### Check Authenticate Only Keyword: {incoming_msg}", flush=True)
                return authenticate_only_command(resp, user_id)

            elif is_authenticating_test:
                print(f"########### Check Authenticate Test Keyword: {incoming_msg}", flush=True)
                is_test = True
                use_test_account(user_id)
                resp.message(using_test_calendar)
                return str(resp)
            
            elif is_whitelisting:
                print(f"########### Check Whitelisting Keyword: {incoming_msg}", flush=True)
                return whitelist_admin_command(incoming_msg, resp, user_id)       

            elif is_revoking:
                print(f"########### Check Revoking Keyword: {incoming_msg}", flush=True)
                return revoke_access_command(resp, user_id)

            else:
                print(f"########### Verify Oauth: {user_id}", flush=True)
                oauth_connection_verification = verify_oauth_connection(user_id)
                print(f"########### Verified OAuth connection: {user_id}, {oauth_connection_verification}", flush=True)
                if oauth_connection_verification == False:
                    try:
                        update_send_test_calendar_message(resp, using_test_calendar, user_id)
                    except Exception as e:
                        print(f"########### ERROR updating send test calendar message: {e}", flush=True)

        except Exception as e:
            resp.message("Error during authentication. Please try again.")
            print(f"########### ERROR in authentication: {e}", flush=True)
            return str(resp)
    
        image_data_url = get_image_data_url(media_url, content_type) if is_image else None
        voice_data_filename = get_voice_data_url(media_url, content_type, user_id) if is_audio else None

        print(f"########### Starting process: {incoming_msg}, {user_id}, image: {bool(image_data_url)}, voice: {bool(voice_data_filename)}", flush=True)

        delete_user_memory(user_id)

        reply_text = summarize_event(resp, user_id, incoming_msg, is_test, image_data_url, voice_data_filename)

        if not isinstance(reply_text, str):
            reply_text = str(reply_text)

        if len(reply_text) > 1400:
            reply_text = trim_reply(reply_text)
            send_whatsapp_message(record_user_id, reply_text)
        else:
            send_whatsapp_message(record_user_id, reply_text)

        print(f"########### End process {user_id}. Response: {reply_text}", flush=True)

        deduct_chat_balance(user['user_details'], user_id)
        add_user_memory(user_id, incoming_msg, reply_text)

        return str(resp)
    
    except Exception as e:
        print(f"######## ERROR processing webhook: {e}", flush=True)
        resp = MessagingResponse()
        resp.message(f"We are sorry, the bot is currently unavailable or under maintenance. Please try again later.")
        return str(resp)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)