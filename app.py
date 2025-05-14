import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from flask import Flask, request, jsonify
from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client
from threading import Thread
from full_model import summarize_event, check_timezone

from flask import request
import requests
import base64

app = Flask(__name__)

@app.route("/")
def root():
    return "Instant Immigration Bot API is running."

@app.route('/webhook', methods=['POST'])
def receive_whatsapp():
    try:
        incoming_msg = request.values.get("Body", "").strip()
        user_id = request.values.get("From", "").strip()
        media_url = request.form.get("MediaUrl0")
        content_type = request.form.get("MediaContentType0") 

        resp = MessagingResponse()
        if media_url:
            response = requests.get(media_url)
            image_data = base64.b64encode(response.content).decode('utf-8')

            image_data_url = f"data:{content_type};base64,{image_data}"
        else:
            image_data_url = None
        
        print(f"########### Starting process: {incoming_msg}, {user_id}, image: {image_data_url}")
        reply_text = summarize_event(user_id, incoming_msg, image_data_url)
        resp.message(reply_text)
        return str(resp)
    except Exception as e:
        print(f"######## ERROR processing webhook: {e}")
        resp = MessagingResponse()
        resp.message(f"We are sorry, the bot is currently unavailable or under maintenance. Please try again later.")
        return str(resp)