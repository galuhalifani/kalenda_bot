import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from flask import Flask, request, jsonify, redirect, session
from google_auth_oauthlib.flow import Flow
from twilio.twiml.messaging_response import MessagingResponse
from creds import *
from keywords import *
from model import summarize_event, mode
from helpers import extract_emails, extract_phone_number, get_image_data_url, send_whatsapp_message, get_voice_data_url
from auth import verify_auth_token_link, verify_oauth_connection, save_token, get_credentials, generate_auth_link
from database import check_user, check_user_balance, deduct_chat_balance, use_test_account, check_user_active_email, update_user_whitelist_status, update_send_whitelisted_message_status, add_user_whitelist_status, update_send_test_calendar_message
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
        print(f"########### Auth request: {user_id}, {token}", flush=True)
        verification = verify_auth_token_link(user_id, token)

        print(f"########### Verification result: {verification}", flush=True)
        if verification != 'verified':
            return verification
        
        session['user_id'] = user_id
        credentials = get_credentials()
        print(f"########### Credentials: {credentials}", flush=True)
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
            save_token(user_id, creds)
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
        is_audio = False
        is_image = False

        if content_type:
            is_audio = bool(media_url) and content_type.startswith("audio/")
            is_image = bool(media_url) and content_type.startswith("image/")

        resp = MessagingResponse()
        is_test = False
        
        try:
            user = check_user(user_id)
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
            if lower_incoming_msg.startswith(authenticate_keyword):
                authenticate_args = incoming_msg.split(authenticate_keyword)
                
                if len(authenticate_args) > 1: # if authenticate <email>
                    user_email = extract_emails(authenticate_args)
                    if user_email:
                        try:
                            is_whitelisted = check_user_active_email(user_id, user_email)
                            if not is_whitelisted:
                                add_user_whitelist_status(user_id, user_email)
                                send_whatsapp_message(ADMIN_NUMBER, "New user request for whitelisting: " + user_email)
                                resp.message("✅ Your email has been added to the whitelist. You will receive a confirmation message once it's approved.")
                                return str(resp)
                            else:
                                resp.message(f"❌ This email is already whitelisted. Click to connect your Google Calendar:\n\n{auth_link}")
                                return str(resp)
                        except Exception as e:
                            print(f"########### Error adding user whitelist status: {e}", flush=True)
                            resp.message("❌ Error adding your email to the whitelist. Please try again.")
                            send_whatsapp_message(ADMIN_NUMBER, {user_id, user_email, incoming_msg, e})
                            return str(resp)

                # if just authenticate
                has_active_email = check_user_active_email(user_id)
                if has_active_email == True:
                    auth_link = generate_auth_link(user_id)
                    resp.message(f"🔐 Click to connect your Google Calendar:\n{auth_link}\n\n. You can only connect to calendar under your e-mail that has been whitelisted. To connect to another calendar, type 'authenticate <email-address>'")
                    return str(resp)
                elif has_active_email == False:
                    resp.message("❌ Your email is not yet whitelisted. Please type 'authenticate <your-google-calendar-email>' to whitelist your email")
                    return str(resp)
                else:
                    resp.message("Your email is pending for whitelisting. We will get back to you in 24h or less. For any questions, reach out to admin at galuh.adika@gmail.com.")
                    return str(resp)

            elif lower_incoming_msg == "authenticate test":
                is_test = True
                use_test_account(user_id)
                resp.message(using_test_calendar)
                return str(resp)
            
            elif lower_incoming_msg.startswith(WHITELIST_KEYWORD):
                email = incoming_msg.split(" ")[1]
                user_number = update_user_whitelist_status(email, True)
                if user_number:
                    try:
                        whatsapp_number = f"whatsapp:{user_number}"
                        auth_link = generate_auth_link(user_number)
                        instruction_text = f"✅ Your email {email} has been whitelisted. You can now connect your Google Calendar.\n\nClick to connect your Google Calendar:\n{auth_link}"
                        send_whatsapp_message(whatsapp_number, instruction_text)
                        send_whatsapp_message(ADMIN_NUMBER, f"email {email} has been whitelisted and user {user_number} has been notified.")
                        update_send_whitelisted_message_status(user_number)
                    except Exception as e:
                        print(f"########### Error sending whitelisted success message: {str(e)}", flush=True)                    

            else:
                oauth_connection_verification = verify_oauth_connection(user_id)
                print(f"########### Verified OAuth connection: {user_id}, {oauth_connection_verification}", flush=True)
                if oauth_connection_verification == False:
                    update_send_test_calendar_message(resp, using_test_calendar, user_id)
        except Exception as e:
            resp.message("Error during authentication. Please try again.")
            print(f"########### ERROR in authentication: {e}", flush=True)
            return str(resp)
    
        image_data_url = get_image_data_url(media_url, content_type) if is_image else None
        voice_data_filename = get_voice_data_url(media_url, content_type, user_id) if is_audio else None

        print(f"########### Starting process: {incoming_msg}, {user_id}, image: {image_data_url}, voice: {voice_data_filename}", flush=True)

        delete_user_memory(user_id)

        reply_text = summarize_event(resp, user_id, incoming_msg, is_test, image_data_url, voice_data_filename)
        if not isinstance(reply_text, str):
            reply_text = str(reply_text)  # or a fallback message
        
        is_too_long = len(reply_text) > 1400

        if is_too_long:
            max_length=1400
            split = [reply_text[i:i+max_length] for i in range(0, len(reply_text), max_length)]
            trimmed_reply = split[0]
            reply_text = f"Your list is too long, I can only show partial results. For more complete list, please specify a shorter date range.\n\n {trimmed_reply}"
            send_whatsapp_message(record_user_id, reply_text)
            print(f"########### trimmed REPLY: {trimmed_reply}", flush=True)
        else:
            print(f"########### REPLY: {reply_text}", flush=True)
            send_whatsapp_message(record_user_id, reply_text)
            print(f"########### REPLY sent: {reply_text}", flush=True)

        print(f"########### End process {user_id}", flush=True)

        try:
            deduct_chat_balance(user['user_details'], user_id)
            print(f"########### Balance deducted", flush=True)
        except Exception as e:
            print(f"####### Error deducting chat balance: {str(e)}")

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