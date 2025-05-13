from __future__ import print_function
import sys
import os
from threading import Thread
from deep_translator import GoogleTranslator
from langdetect import detect
import pandas as pd
from pymongo import MongoClient
import openai
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
import pytz
from twilio.rest import Client
import os.path
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from cal import get_calendar_service, get_upcoming_events
from datetime import datetime, timedelta

load_dotenv(override=True)
MONGODB_URL=os.getenv('MONGO_URI')
OPENAI_KEY=os.getenv('OPENAI_KEY')

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
else:
    user_collection = None

SCOPES = ['https://www.googleapis.com/auth/calendar.events']

def get_calendar_service():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)

        # Save the token for future use
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    service = build('calendar', 'v3', credentials=creds)
    return service

def get_upcoming_events():
    service = get_calendar_service()
    now = datetime.datetime.now().isoformat() + 'Z'
    end_of_tomorrow = now + datetime.timedelta(days=2).isoformat() + 'Z'

    events_result = service.events().list(
        calendarId='primary', 
        timeMin=now,
        timeMax=end_of_tomorrow,
        singleEvents=True,
        orderBy='startTime'
    ).execute()

    events = events_result.get('items', [])

    if not events:
        print("No upcoming events found.")
        return []
    else:
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            print(f"{start} - {event['summary']}")
        return events

def save_event_to_calendar(instruction):
    service = get_calendar_service()
    event_details = instruction.split('add_event: ')[1].split('}')[0] + '}'

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
        print(f"Error updating timezone for user {user_id}:", e)
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
    print(f'####### full response: {llm}')
    response = llm['choices'][0]['message']['content']
    return response

def summarize_event(user_id, input, image_data_url=None):
    try:
        instruction = init_llm(user_id, input, image_data_url)
        if isinstance(instruction, str) and instruction.startswith('add_event:'):
            try:
                new_event = save_event_to_calendar(instruction)
                return new_event
            except Exception as e:
                print(f"########### Error adding to g-cal: {str(e)}")
                return "Sorry, I couldn not add the event to your calendar."
        
        elif isinstance(instruction, str) and instruction.startswith('retrieve_event:'):
            try:
                events = get_upcoming_events()
                return events
            except Exception as e:
                print(f"########### Error retrieving events: {str(e)}")
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
                print(f"########### Error updating timezone: {str(e)}")
                return "Sorry, I could not set your timezone. Please try again."
        else:
            return instruction
    except Exception as e:
        print(f"########### Error processing instruction: {str(e)}")
        return "Sorry, I could not process your request. Please try again."
