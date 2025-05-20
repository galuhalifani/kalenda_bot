import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from flask import Flask, request, jsonify, redirect, session, render_template_string, render_template
from google_auth_oauthlib.flow import Flow
from twilio.twiml.messaging_response import MessagingResponse
from creds import *
from keywords import *
from model import summarize_event, mode
from helpers import extract_emails, extract_phone_number, get_image_data_url, send_whatsapp_message, get_voice_data_url, trim_reply
from auth import verify_auth_token_link, verify_oauth_connection, save_token, get_credentials, generate_auth_link, authenticate_command, authenticate_only_command, whitelist_admin_command
from database import add_pending_auth, get_pending_auth, check_user, check_user_balance, deduct_chat_balance, use_test_account, check_user_active_email, update_user_whitelist_status, update_send_whitelisted_message_status, add_user_whitelist_status, update_send_test_calendar_message, revoke_access_command
from text import greeting, using_test_calendar
from session_memory import delete_user_memory, add_user_memory
import secrets
from flask import request
import markdown

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", secrets.token_hex(16))
pending_auth = {}

@app.route("/")
def root():
    return render_template("index.html")
    
@app.route("/about")
def home():
    with open("docs/index.md", "r", encoding="utf-8") as f:
        md_content = f.read()
        html_content = markdown.markdown(md_content)
        return render_template_string("""
        <html>
        <head><title>About</title></head>
        <body>{{ content|safe }}</body>
        </html>
        """, content=html_content)

@app.route("/privacy")
def privacy():
    with open("docs/PRIVACY.md", "r", encoding="utf-8") as f:
        md_content = f.read()
        html_content = markdown.markdown(md_content)
        return render_template_string("""
        <html>
        <head><title>Privacy Policy</title></head>
        <body>{{ content|safe }}</body>
        </html>
        """, content=html_content)

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
        add_pending_auth(user_id, state)
        print("########### SESSION CONTENT auth:", dict(session), flush=True)
        return redirect(auth_url)
    except Exception as e:
        print(f"########### ERROR in auth: {e}", flush=True)
        return "❌ Error during authentication. Please try again."

@app.route("/oauthcallback")
def oauth_callback():
    print(f"########### OAuth callback triggered", flush=True)
    try:
        print("########### SESSION CONTENT callback:", dict(session), flush=True)
        state_from_query = request.args.get("state")
        if not state_from_query:
            raise Exception("Missing OAuth state")
        
        state = session.get("state") 
        user_id = session.get("user_id")

        if not state or not user_id:
            auth_data = get_pending_auth(state_from_query)
            if not auth_data:
                raise Exception("Invalid or expired state")
            state = auth_data['state']
            user_id = auth_data['user_id']
        
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
            if is_authenticating:
                email = incoming_msg[len("authenticate"):].strip()
                
                if email: # if authenticate <email>
                    return authenticate_command(incoming_msg, resp, user_id)
                else:
                    # if just authenticate
                    return authenticate_only_command(resp, user_id)

            elif is_authenticating_test:
                is_test = True
                use_test_account(user_id)
                resp.message(using_test_calendar)
                return str(resp)
            
            elif is_whitelisting:
                return whitelist_admin_command(incoming_msg, resp, user_id)       

            elif is_revoking:
                return revoke_access_command(resp, user_id)

            else:
                oauth_connection_verification = verify_oauth_connection(user_id)
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