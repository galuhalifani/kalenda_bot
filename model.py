from __future__ import print_function
import sys
import os
from threading import Thread
import pandas as pd
from pymongo import MongoClient
from openai import OpenAI
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler
import pytz
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse
import os.path
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from datetime import datetime, timedelta, timezone as tzn
import json
from cryptography.fernet import Fernet
import secrets
import requests
import base64
from requests.auth import HTTPBasicAuth
import re
from creds import *
from database import user_collection, tokens_collection, check_user, check_timezone, add_update_timezone, deduct_chat_balance, check_user_balance
from auth import decrypt_token, encrypt_token, save_token
from helpers import clean_instruction_block, readable_date, clean_description, extract_phone_number, get_image_data_url, split_message,send_whatsapp_message
from calendar_service import get_user_calendar_timezone, get_calendar_service, save_event_to_draft, save_event_to_calendar, get_upcoming_events, update_event_draft, transform_events_to_text
from session_memory import session_memories, get_user_memory, max_chat_stored
from prompt import prompt_init

if mode == 'test':
    os.environ["SSL_CERT_FILE"] = r"C:\Users\galuh\miniconda\envs\py10\Library\ssl\cacert.pem"

def init_llm(user_id, input, image_data_url=None, user_timezone=None):
    try:
        print(f"########### Timezone: {user_timezone}", flush=True)
        user_latest_event_draft = None
        latest_conversations = None

        for memory in session_memories:
            _, memory = get_user_memory(user_id)
            if memory:
                latest_draft = memory['latest_event_draft'] if memory['latest_event_draft'] else None
                print(f"########### Latest draft: {latest_draft}", flush=True)
                latest_draft_status = latest_draft['status'] if latest_draft else None
                print(f"########### Latest draft status: {latest_draft_status}", flush=True)
                user_latest_event_draft = latest_draft if latest_draft_status == 'draft' else None
                print(f"########### User latest event draft: {user_latest_event_draft}", flush=True)
                latest_conversations = memory['latest_conversations'] if memory['latest_conversations'] else None

        prompt = prompt_init(input, datetime.now(tzn.utc), user_timezone, user_latest_event_draft, latest_conversations)
        print(f"########### Prompt: {prompt}", flush=True)

        try:
            client = OpenAI()
            print("✅ OpenAI client initialized", flush=True)
        except Exception as e:
            print(f"❌ Error initializing OpenAI client: {e}", flush=True)
            return "Sorry, I couldn't connect to the OpenAI service. Please try again later."

        messages=[{
                'role': 'user',
                'content': [
                    {
                        "type": "text",
                        "text": prompt
                    }
                ]
            }]
        
        if image_data_url:
            print(f"########### Entering with Image data URL: {image_data_url}", flush=True)
            messages[0]['content'].append({
                "type": "image_url",
                "image_url": {"url": image_data_url}
        })
            
        llm = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            temperature=0,
            max_tokens=1000
        )

        print(f'####### full response: {llm}', flush=True)
        response = llm.choices[0].message.content
        return response
    except Exception as e:
        print(f"########### Error in LLM: {str(e)}", flush=True)
        return "Sorry, I couldn't process your request. Please try again."

def summarize_event(resp, user_id, input, is_test=False, image_data_url=None):
    cal_timezone = get_user_calendar_timezone(user_id, is_test)
    user_timezone = check_timezone(user_id, cal_timezone)
    raw_answer = init_llm(user_id, input, image_data_url, user_timezone)

    print(f"########### Answer: {raw_answer}", flush=True)
    answer = clean_instruction_block(raw_answer)

    whatsappNum = f'whatsapp:+{user_id}'
    if isinstance(answer, str) and 'add_event:' in answer.strip():
        print(f"########### Adding event: {answer}", flush=True)
        try:
            loading_message = "Adding your event..."
            # resp.message(loading_message)
            send_whatsapp_message(f'{whatsappNum}', loading_message)
        except Exception as e:
            print(f"########### Error sending loading message: {str(e)}", flush=True)
        try:
            new_event = save_event_to_calendar(answer, user_id, is_test)
            return new_event
        except Exception as e:
            print(f"########### Error adding to g-cal: {str(e)}", flush=True)
            return "Sorry, I couldn not add the event to your calendar."
        
    elif isinstance(answer, str) and 'draft_event:' in answer.strip():
        print(f"########### Drafting event: {answer}", flush=True)
        try:
            loading_message = "Drafting..."
            # resp.message(loading_message)
            send_whatsapp_message(f'{whatsappNum}', loading_message)
        except Exception as e:
            print(f"########### Error sending loading message: {str(e)}", flush=True)
        try:
            text_reply = save_event_to_draft(answer, user_id)
            print(f"########### Replying event draft: {text_reply}", flush=True)
            return text_reply
        except Exception as e:
            print(f"########### Error parsing event details: {str(e)}", flush=True)
            return "Sorry, I couldn't understand the event details."
        
    elif isinstance(answer, str) and 'retrieve_event:' in answer.strip():
        print(f"########### Retrieving events: {answer}", flush=True)
        try:
            loading_message = "Fetching your events..."
            # resp.message(loading_message)
            send_whatsapp_message(f'{whatsappNum}', loading_message)
        except Exception as e:
            print(f"########### Error sending loading message: {str(e)}", flush=True)
        try:
            events = get_upcoming_events(answer, user_id, is_test)
            print(f"########### All list of Events: {events}", flush=True)
            user_events = transform_events_to_text(events, user_timezone)
            return user_events
        except Exception as e:
            print(f"########### Error retrieving events: {str(e)}", flush=True)
            return "Sorry, I am unable to fetch your events at the moment."

    elif isinstance(answer, str) and 'timezone_set:' in answer.strip():
        print(f"########### Setting timezone: {answer}", flush=True)
        try:
            new_timezone = answer.split('timezone_set: ')[1].strip()
            updated_timezone = add_update_timezone(user_id, new_timezone)
            if updated_timezone:
                return f'Your timezone has been changed to {new_timezone}. Please proceed with your request.'
            else:
                return f'Failed to set your timezone. Please try again.'
        except Exception as e:
            print(f"########### Error updating timezone: {str(e)}", flush=True)
            return "Sorry, I could not set your timezone. Please try again."
        
    elif isinstance(answer, str) and answer.strip().startswith("Event not added"):
        print(f"########### Event not added: {answer}", flush=True)
        return "Sorry, I'm unable to assist you with this event. Please start over with more details."
    
    else:
        print(f"########### Instruction not recognized: {answer}", flush=True)
        return answer