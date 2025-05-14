import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from flask import Flask, request, jsonify, redirect, session
from google_auth_oauthlib.flow import Flow
from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client
from threading import Thread
from full_model import summarize_event, check_timezone, get_credentials, SCOPES, REDIRECT_URI, save_token, generate_auth_link, verify_auth_token, verify_oauth_connection, use_test_account
import secrets

from flask import request
import requests
import base64

app = Flask(__name__)

@app.route("/")
def root():
    return "Kalenda Bot API is running."

@app.route("/auth")
def auth():
    try:
        user_id = request.args.get("user_id")
        token = request.args.get("token")
        verification = verify_auth_token(user_id, token)

        if verification != 'verified':
            return verification
        
        session['user_id'] = user_id
        credentials = get_credentials()
        flow = Flow.from_client_config(
            credentials,
            scopes=SCOPES,
            redirect_uri=REDIRECT_URI
        )
        auth_url, state = flow.authorization_url(prompt='consent')
        session["state"] = state
        return redirect(auth_url)
    except Exception as e:
        print(f"########### ERROR in auth: {e}", flush=True)
        return "❌ Error during authentication. Please try again."

@app.route("/oauthcallback")
def oauth_callback():
    try:
        state = session["state"]
        user_id = session["user_id"]
        credentials = get_credentials()
        flow = Flow.from_client_config(
            credentials,
            scopes=["https://www.googleapis.com/auth/calendar.events"],
            state=state,
            redirect_uri=REDIRECT_URI #/oauthcallback route
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
        user_id = request.values.get("From", "").strip()
        media_url = request.form.get("MediaUrl0")
        content_type = request.form.get("MediaContentType0") 

        resp = MessagingResponse()
        is_test = False
        
        if incoming_msg == "authenticate":
            auth_link = generate_auth_link(user_id)
            resp.message(f"🔐 Click to connect your Google Calendar:\n{auth_link}")
            return str(resp)
        elif incoming_msg == "authenticate test":
            is_test = True
            use_test_account(user_id)
            resp.message(
                "🔧 You've been connected to our public test calendar.\n\n"
                "You can access and view calendar here:\n"
                "📅 https://calendar.google.com/calendar/embed?src=kalenda.bot%40gmail.com \n\n"
                "You can use this bot to add a new event via text or image, and retrieve events of today and tomorrow\n"
                "If you wish to connect your own calendar, please type 'authenticate' to get started.\n\n"
            )
            return str(resp)
        else:
            oauth_connection_verification = verify_oauth_connection(user_id)
            if not oauth_connection_verification:
                resp.message("❌ You need to connect your Google Calendar first. Please type 'authenticate' to get the link, or type 'authenticate test' to use joint testing calendar")
                return str(resp)
    
        if media_url:
            response = requests.get(media_url)
            image_data = base64.b64encode(response.content).decode('utf-8')

            image_data_url = f"data:{content_type};base64,{image_data}"
        else:
            image_data_url = None
        
        print(f"########### Starting process: {incoming_msg}, {user_id}, image: {image_data_url}", flush=True)
        reply_text = summarize_event(user_id, incoming_msg, is_test, image_data_url)
        resp.message(reply_text)
        return str(resp)
    except Exception as e:
        print(f"######## ERROR processing webhook: {e}", flush=True)
        resp = MessagingResponse()
        resp.message(f"We are sorry, the bot is currently unavailable or under maintenance. Please try again later.")
        return str(resp)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)