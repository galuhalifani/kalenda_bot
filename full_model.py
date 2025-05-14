from __future__ import print_function
import sys
import os
from threading import Thread
import pandas as pd
from pymongo import MongoClient
import openai
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler
import pytz
from twilio.rest import Client
import os.path
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from datetime import datetime, timedelta
import json
from cryptography.fernet import Fernet
import secrets
import pickle

load_dotenv(override=True)
MONGODB_URL=os.getenv('MONGO_URI')
OPENAI_KEY=os.getenv('OPENAI_API_KEY')
CLIENT_ID = os.environ["GOOGLE_CLIENT_ID"]
CLIENT_SECRET = os.environ["GOOGLE_CLIENT_SECRET"]
TEST_CLIENT_ID = os.environ["TEST_CLIENT_ID"]
TEST_CLIENT_SECRET = os.environ["TEST_CLIENT_SECRET"]
TOKEN_URI = os.environ["TOKEN_URI"]
AUTH_URI = os.environ["AUTH_URI"]
CONNECT_AUTH_URI = os.environ["CONNECT_AUTH_URI"]
REDIRECT_URI = os.environ["REDIRECT_URI"]
SCOPES = ['https://www.googleapis.com/auth/calendar.events']

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

def init_mongodb():
    try:
        client = MongoClient(MONGODB_URL, serverSelectionTimeoutMS=5000)
        client.server_info()
        return client
    except Exception as e:
        error_msg = f"⚠️ Failed connecting to database: {str(e)}"
        return error_msg
    
client = init_mongodb()
if client:
    db = client['kalenda']
    user_collection = db['user']
    tokens_collection = db['tokens']
else:
    user_collection = None
    tokens_collection = None

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

def get_calendar_service(user_id, is_test=False):
    user_token = tokens_collection.find_one({"user_id": user_id})

    is_using_test_account = user_token.get("is_using_test_account", True) or is_test

    if not user_token:
        message = "User not authenticated. Type 'authenticate' to connect to your Google Calendar, or type 'authenticate test' to use joint testing calendar."
        raise Exception(message)
    
    access_token = user_token.get("access_token")
    refresh_token = user_token.get("refresh_token")

    creds = Credentials(
        token=decrypt_token(access_token),
        refresh_token=decrypt_token(refresh_token),
        token_uri=TOKEN_URI,
        client_id=TEST_CLIENT_ID if is_using_test_account else CLIENT_ID,
        client_secret=TEST_CLIENT_SECRET if is_using_test_account else CLIENT_SECRET,
        scopes=SCOPES
    )

    is_creds_expired = creds.expired and creds.refresh_token
    if is_creds_expired:
        creds.refresh(Request())
        tokens_collection.update_one(
            {"user_id": user_id},
            {"$set": {
                "access_token": encrypt_token(creds.token), 
                "expiry": creds.expiry.isoformat()}}
        )
        if is_using_test_account:
            tokens_collection.update_one(
                {"user_id": "test_shared_calendar"},
                {"$set": {
                    "access_token": encrypt_token(creds.token), 
                    "expiry": creds.expiry.isoformat()}}
        )

    service = build('calendar', 'v3', credentials=creds)
    return service
    
def list_calendars(service):
    calendar_list = service.calendarList().list().execute()
    return calendar_list

def get_upcoming_events(user_id, is_test=False):
    service = get_calendar_service(user_id, is_test)
    now = datetime.now()
    end_of_tomorrow = now + timedelta(days=2)

    now_str = now.isoformat() + 'Z'
    end_of_tomorrow_str = end_of_tomorrow.isoformat() + 'Z'

    try:
        calendars = list_calendars(service)
    except Exception as e:
        print(f"########### Error retrieving calendar list: {str(e)}")
        calendars = None

    all_events = []
    if not calendars:
        events_result = service.events().list(
            calendarId='primary', 
            timeMin=now_str,
            timeMax=end_of_tomorrow_str,
            singleEvents=True,
            orderBy='startTime'
        ).execute()

        events = events_result.get('items', [])
        print(f"########### Calendar events: {events}")

        if not events:
            print("No upcoming events found.")
            return []
        else:
            for event in events:
                start = event['start'].get('dateTime', event['start'].get('date'))
                print(f"{start} - {event['summary']}")
        return events
    
    else:
        for calendar in calendars['items']:
            calendar_id = calendar['id']
            events_result = service.events().list(
                calendarId=calendar_id, 
                timeMin=now_str,
                timeMax=end_of_tomorrow_str,
                singleEvents=True,
                orderBy='startTime'
            ).execute()

            events = events_result.get('items', [])
            print(f"########### Calendar events: {events}")

            if not events:
                print("No upcoming events found.")
                continue
            else:
                for event in events:
                    all_events.append({
                        "calendar": calendar['summary'],
                        "start": event['start'].get('dateTime', event['start'].get('date')),
                        "summary": event.get('summary', '(No Title)')
                    })
        return all_events

def save_event_to_calendar(instruction, user_id, is_test=False):
    service = get_calendar_service(user_id, is_test)

    try:
        json_str = instruction.split('add_event:')[1].strip()
        print(f"####### JSON string: {json_str}")
        event_details = json.loads(json_str)
    except Exception as e:
        print(f"####### Failed to parse event JSON: {e}")
        return "Sorry, I couldn't understand your event details."

    name = event_details['name']
    start_date_str = event_details['start_date']
    end_date_str = event_details['end_date']
    start_date = datetime.fromisoformat(start_date_str)
    end_date = (start_date + timedelta(hours=1)) if end_date_str is None else datetime.fromisoformat(end_date_str)
    timezone = event_details['timezone'] if event_details['timezone'] else 'Asia/Jakarta'
    location = event_details['location']
    description = event_details['description']
    participants = event_details['participants']
    reminder_minutes = event_details['reminder']

    attendees = []
    for participant in participants:
        attendees.append({'email': participant})

    if not reminder_minutes:
        reminder = {
            'useDefault': True,
        }
    else:
        reminder = {
                'overrides': [
                    {'method': 'email', 'minutes': reminder_minutes},
                    {'method': 'popup', 'minutes': reminder_minutes},
                ],
            }

    event = {
        'summary': name,
        'location': location,
        'description': description,
        'start': {
            'dateTime': start_date.isoformat(),
            'timeZone': timezone,
        },
        'end': {
            'dateTime': end_date.isoformat(),
            'timeZone': timezone,
        },
        'attendees': attendees,
        'reminders': reminder,
        "visibility": "default",

    }

    try:
        new_event = service.events().insert(calendarId='primary', body=event).execute()    
        return new_event
    except Exception as e:
        print(f"########### Error adding to g-cal: {str(e)}")
        return None

def prompt_init(input, timezone=None):
    PROMPT = f'''
    You are a scheduler assistant. Your main task is to help manage user's schedule. 
    You will be given an instruction by the user to either add an event to the calendar or retrieve events from the calendar.
    You will also receive either a text, image, or both as input.
    
    Timezone rules:
    - If the input contains timezone, you will use that timezone to schedule the event. If the timezone is in a human language format, which you will need to convert to a standard timezone format (e.g., "America/New_York" or "Asia/Jakarta").
    - If the input does not contain timezone, you will use {timezone} as the timezone.
    - If {timezone} is None, you will respond with "You have not set your timezone yet. Please provide your timezone." and stop the process.
    - If the user input is only about timezone (no other event details added), you will respond with "timezone_set: timezone" with timezone being the standard timezone format, and stop the process.
    - If the user input is only about timezone but you are unable to interpret the timezone, you will respond with "Timezone not recognized, please try again" and stop the process.

    Input rules:
    - If the input is a text, you will process the text and respond with the appropriate action.
    - If the input is an image, you will process the image and respond with the appropriate action.
    - If the input is both text and image, you will process the text first and then the image.
    - Only proceed with the below actions after going through the timezone and input rules.

    - If user asks to add an event, you need to respond with USER FORMAT:
        1. The event name
        2. The event date, time, and timezone. If user does not add timezone in event details, you will use {timezone}.
        3. The event location
        4. The event description
        5. The event reminder (if available)
        6. The event participants (write all the participants emails, or omit if not available)
    
    Then ask the user to confirm the event details. If the user confirms, you will respond SYSTEM FORMAT:
        'add_event: {
            "name": name,
            "start_date": start_date,
            "end_date": end_date,
            "timezone": timezone,
            "location": location,
            "description": description,
            "reminder": reminder (convert to minutes, write 0 if not available),
            "participants": participants (in a list format)
        }'

    If the user doesn't confirm, you will ask user to specify the correct details, revise the event details, return the corrected USER FORMAT, and ask for confirmation again (repeat the process until user confirms).
    If after three revision attempts the user doesn't confirm, you will respond with "Event not added" and stop the process.

    - If user asks to retrieve events, you need to respond "Retrieve Events" of the today and tomorrow with format:
    'retrieve_event'

    - If user only sends an image without instructional text, you will assume that the user wants to add an event and proceed with the flow of adding an event.
    
    When returning the event date and time, format it in ISO 8601 with time zone offset (e.g., "2025-05-13T10:00:00+07:00").

    Question: {input}
    Answer:
    '''
    return PROMPT

def check_timezone(user_id):
    user = user_collection.find_one({"user_id": user_id})
    if (user):
        timezone = user.get("timezone")
        if timezone:
            return timezone
        else:
            return None
    else:
        return None

def add_update_timezone(user_id, timezone):
    try:
        user_collection.update_one(
                {"user_id": user_id},
                {
                    "$set": {"timezone": timezone}
                },
                upsert=True
            )
        return True
    except Exception as e:
        print(f"Error updating timezone for user {user_id}: {e}", flush=True)
        return False

def init_llm(user_id, input, image_data_url=None):
    timezone = check_timezone(user_id)
    prompt = prompt_init(input, timezone)

    llm = openai.chatCompletion.create(
        model="gpt-4-vision-preview",
        messages=[{
            'role': 'user',
            'content': [
                {
                    "type": "text",
                    "text": prompt
                },
                {
                    "type": "image_url",
                    "image_url": {"url": image_data_url}
                }
            ]
        }],
        temperature=0,
        max_tokens=1000
    )
    print(f'####### full response: {llm}', flush=True)
    response = llm['choices'][0]['message']['content']
    return response

def summarize_event(user_id, input, is_test=False, image_data_url=None):
    try:
        instruction = init_llm(user_id, input, image_data_url)
        if isinstance(instruction, str) and instruction.startswith('add_event:'):
            try:
                new_event = save_event_to_calendar(instruction, user_id, is_test)
                return new_event
            except Exception as e:
                print(f"########### Error adding to g-cal: {str(e)}", flush=True)
                return "Sorry, I couldn not add the event to your calendar."
        
        elif isinstance(instruction, str) and instruction.startswith('retrieve_event:'):
            try:
                events = get_upcoming_events(user_id, is_test)
                return events
            except Exception as e:
                print(f"########### Error retrieving events: {str(e)}", flush=True)
                return "Sorry, I am unable to fetch your events at the moment."

        elif isinstance(instruction, str) and instruction.startswith('timezone_set:'):
            try:
                timezone = instruction.split('timezone_set: ')[1].strip()
                updated_timezone = add_update_timezone(user_id, timezone)
                if updated_timezone:
                    return f'Thank you for providing your timezone. Your timezone has been set to {timezone}. Please proceed with your event details.'
                else:
                    return f'Failed to set your timezone. Please try again.'
            except Exception as e:
                print(f"########### Error updating timezone: {str(e)}", flush=True)
                return "Sorry, I could not set your timezone. Please try again."
        else:
            return instruction
    except Exception as e:
        print(f"########### Error processing instruction: {str(e)}", flush=True)
        return "Sorry, I could not process your request. Please try again."

def generate_auth_link(user_id):
    token = secrets.token_hex(16)
    expires = datetime.now() + timedelta(minutes=30)

    tokens_collection.update_one(
        {"user_id": user_id},
        {"$set": {
            "auth_token_link": token,
            "auth_token_link_expiry": expires.isoformat()
        }},
    upsert=True
    )

    return f"{CONNECT_AUTH_URI}?user_id={user_id}&token={token}"

def verify_auth_token(user_id, token):
    record = tokens_collection.find_one({"auth_token_link": token})
    record_user_id = record.get("user_id") if record else None

    token_is_valid = record_user_id == user_id

    if not record or not token_is_valid:
        return "❌ Invalid link. Please try again. Type 'authenticate' to generate a new link."
    
    if datetime.now() > datetime.fromisoformat(record["auth_token_link_expiry"]):
        return "❌ Link is expired. Please try again. Type 'authenticate' to generate a new link."
    
    return "verified"

def verify_oauth_connection(user_id):
    user_token = tokens_collection.find_one({"user_id": user_id, "refresh_token": {"$exists": True}})
    if not user_token:
        return False
    
    return True

def use_test_account(user_id):
    test_tokens = tokens_collection.find_one({"user_id": 'test_shared_calendar'})
    if not test_tokens:
        raise Exception("Test account not found in database.")

    test_access_token = test_tokens.get("access_token")
    test_refresh_token = test_tokens.get("refresh_token")
    test_expiry = test_tokens.get("expiry")

    tokens_collection.update_one(
        {"user_id": user_id},
        {"$set": {
            "access_token": test_access_token,
            "refresh_token": test_refresh_token,
            "scopes": SCOPES,
            "expiry": test_expiry,
            "is_using_test_account": True
        }},
    upsert=True)