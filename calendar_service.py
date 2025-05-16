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
from database import user_collection, tokens_collection
from auth import decrypt_token, encrypt_token, save_token
from helpers import readable_date, convert_timezone, all_valid_emails
from session_memory import latest_event_draft, get_user_memory, session_memories

def get_calendar_service(user_id, is_test=False):
    user_account = user_collection.find_one({"user_id": user_id})

    is_using_test_account = user_account.get("is_using_test_account", True) or is_test
    
    userId = user_id if not is_using_test_account else "test_shared_calendar"
    user_token = tokens_collection.find_one({"user_id": userId})

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
    print("########### creds: ", creds, flush=True)

    is_creds_expired = creds.expired and creds.refresh_token
    if is_creds_expired:
        if is_using_test_account:
            tokens_collection.update_one(
                {"user_id": "test_shared_calendar"},
                {"$set": {
                    "access_token": encrypt_token(creds.token), 
                    "expiry": creds.expiry.isoformat()}}
        )
        else:
            creds.refresh(Request())
            tokens_collection.update_one(
                {"user_id": user_id},
                {"$set": {
                    "access_token": encrypt_token(creds.token), 
                    "expiry": creds.expiry.isoformat()}}
            )
        
    service = build('calendar', 'v3', credentials=creds)
    return service
    
def get_user_calendar_timezone(user_id, is_test=False):
    try:
        service = get_calendar_service(user_id, is_test)
        calendar = service.calendars().get(calendarId='primary').execute()
        return calendar.get('timeZone') 
    except Exception as e:
        print(f"########### Error retrieving calendar timezone: {str(e)}")
        return 'Asia/Jakarta'  # Default timezone

def list_calendars(service):
    calendar_list = service.calendarList().list().execute()
    return calendar_list

def get_upcoming_events(instruction, user_id, is_test=False):
    splitted = instruction.split('retrieve_event:')[1].strip()
    event_details = json.loads(splitted)
    is_period_provided = event_details.get('start', None) or event_details.get('end', None) or event_details.get('q', None)

    print(f"############## IS PERIOD PROVIDED: {is_period_provided}", flush=True)

    request_timezone = event_details.get('timezone', None)

    print(f"########### Event details: {event_details}", flush=True)

    start = event_details.get('start', str(datetime.now(tzn.utc))).strip()
    end_raw = event_details.get('end', None)
    calendar_name_filter = event_details.get('calendar', None)
    q = event_details.get('q', None)

    is_start_not_none = bool(start)
    is_end_not_none = bool(end_raw)

    try:
        start = datetime.fromisoformat(start)
        print('START BEFORE', start, flush=True)
        if (start < datetime.now(tzn.utc)):
            start = datetime.now(tzn.utc)
            print('START AFTER', start, flush=True)
    except ValueError:
        print(f"########### Invalid start date format: {start}", flush=True)
        start = datetime.now()

    end_timedelta = timedelta(days=2) if not q else timedelta(days=30)
    print(f"########### End timedelta: {end_timedelta}", flush=True)
    end = datetime.fromisoformat(end_raw) if is_end_not_none else (start + end_timedelta)
    
    start_str = start.isoformat()
    end_str = end.isoformat()

    service = get_calendar_service(user_id, is_test)

    print(f"########### Start ISO format: {start_str}, End ISO format: {end_str}", flush=True)

    try:
        calendars = list_calendars(service)
    except Exception as e:
        print(f"########### Error retrieving calendar list: {str(e)}")
        calendars = None

    all_events = []
    if not calendars:
        events_result = service.events().list(
            calendarId='primary', 
            timeMin=start_str,
            timeMax=end_str,
            singleEvents=True,
            orderBy='startTime'
        ).execute()

        events = events_result.get('items', [])
        print(f"########### Calendar events: {events}")

        if not events:
            print("No upcoming events found.")
            return {[], is_period_provided}
        else:
            for event in events:
                all_events.append(event)   
    else:
        for calendar in calendars['items']:
            is_primary = calendar.get('primary', False)
            print(f"########### Calendar: {calendar}", flush=True)
            calendar_id = calendar['id']
            calendar_name = 'primary' if is_primary else calendar['summary']

            if calendar_name_filter and (calendar_name.lower() != calendar_name_filter.lower()):
                continue
            
            if q:
                print(f"########### Searching for keyword: {q}", flush=True)
                events_result = service.events().list(
                    calendarId=calendar_id, 
                    timeMin=start_str,
                    timeMax=end_str,
                    singleEvents=True,
                    orderBy='startTime',
                    q=q
                ).execute()
            else:
                print(f"########### No keyword provided, fetching all events", flush=True)
                print(f"########### Calendar ID: {calendar_id}", flush=True)
                print(f"########### Start: {start_str}, End: {end_str}", flush=True)
                events_result = service.events().list(
                    calendarId=calendar_id, 
                    timeMin=start_str,
                    timeMax=end_str,
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
                        "calendar": 'primary' if is_primary else calendar['summary'],
                        **event
                    })
    
    return (all_events, is_period_provided, request_timezone)

def transform_events_to_text(eventList, user_timezone=None):
    print(f"########### Transforming events to text: {eventList}", flush=True)
    events, is_period_provided, request_timezone = eventList

    print(f"########### Events: {events}", flush=True)
    print(f"########### Is period provided: {is_period_provided}", flush=True)
    if not events:
        return "No upcoming events found."
    
    event_list = []
    calendar_list = []
    introduction = "Here is your events for today and tomorrow" if not is_period_provided else "Here are your events"

    tz_to_use = request_timezone if request_timezone else (user_timezone if user_timezone else 'default')
    
    for event in events:
        start = event['start'].get('dateTime', event['start'].get('date'))
        end = event['end'].get('dateTime', event['end'].get('date'))
        summary = event.get('summary', '(No Title)')
        description = event.get('description', '(No Description)')
        location = event.get('location', '')
        displayName = event.get('displayName', '')
        timezone = event['start'].get('timeZone', '') if tz_to_use == 'default' else tz_to_use
        calendar = event.get('calendar', 'primary')

        description = re.sub(r'<.*?>', '', description)        # Clean HTML from description

        is_datetime = event['start'].get('dateTime', None)
        
        try:
            if is_datetime:
                # converting to user's timezone
                start = convert_timezone(start, timezone)
                end = convert_timezone(end, timezone)
        except Exception as e:
            print(f"########### Error converting timezone: {str(e)}")

        start_str = readable_date(start, is_datetime, False)
        end_str = readable_date(end, is_datetime, False)

        if calendar not in calendar_list:
            lines = [f"____________________\n_*Calendar*_: {calendar}\n\n*{summary}*", f"{start_str} - {end_str} {timezone}"]         # Build optional lines only if values exist
            calendar_list.append(calendar)
        else:
            lines = [f"*{summary}*", f"{start_str} - {end_str} {timezone}"]

        if location:
            lines.append(f"Location: {location}")
        if description and description != "(No Description)":
            lines.append(f"Description: {description}")
        if displayName:
            lines.append(f"Calendar: {displayName}")

        event_list.append("\n".join(lines))

    allEvents = f"\n\n".join(event_list)
    return f"{introduction}:\n\n{allEvents}"

def update_event_draft(user_id, new_draft):
    new_draft['status'] = 'draft'
    index, memory = get_user_memory(user_id)
    if memory:
        session_memories[index]['latest_event_draft'] = new_draft
        return session_memories[index]['latest_event_draft']
    else:
        session_memories.append({
            "user_id": user_id,
            "latest_event_draft": new_draft
        })
        return session_memories[-1]['latest_event_draft']

def save_event_to_draft(instruction, user_id):
    print(f"########### save_event_to_draft: {instruction}", flush=True)
    json_str = instruction.split('draft_event:')[1].strip()
    event_details = json.loads(json_str)

    print(f"########### save_event_to_draft Event details: {event_details}", flush=True)

    start_date = readable_date(event_details['start_date'], True)
    end_date = readable_date(event_details['end_date'], True)

    is_start_and_end_same = event_details['start_date'] == event_details['end_date']

    date_range = f"{start_date} - {end_date}" if not is_start_and_end_same else f"{start_date}"

    text_reply = f'''
    Here is your event, please confirm:
    1. *Event Name:* {event_details['name']}
    2. *Event Date and Time:* {date_range}
    3. *Event Location:* {event_details['location']}
    4. *Event Description:* {event_details['description']}
    '''
    num_counter = 4
    if not event_details['participants']:
        num_counter += 1
        indent = ' ' * 4 if num_counter > 5 else ''
        text_reply += f"{indent}{num_counter}. *Participants Emails:* Not added\n"
    if event_details['participants']:
        if not all_valid_emails(event_details['participants']):
            return "Sorry, only emails are allowed for participants list."
        num_counter += 1
        indent = ' ' * 4 if num_counter > 5 else ''
        text_reply += f"{indent}{num_counter}. *Participants Emails:* {', '.join(event_details['participants'])}\n"
    if event_details['timezone']:
        num_counter += 1
        indent = ' ' * 4 if num_counter > 5 else ''
        text_reply += f"{indent}{num_counter}. *Event Timezone:* {event_details['timezone']}\n"
    if event_details['calendar']:
        num_counter += 1
        indent = ' ' * 4 if num_counter > 5 else ''
        text_reply += f"{indent}{num_counter}. *Event Calendar:* {event_details['calendar']}\n"
    if event_details['reminder']:
        num_counter += 1
        indent = ' ' * 4 if num_counter > 5 else ''
        text_reply += f"{indent}{num_counter}. *Event Reminder:* {event_details['reminder']} minutes before the event"
    if event_details['send_updates']:
        num_counter += 1
        indent = ' ' * 4 if num_counter > 5 else ''
        text_reply += f"{indent}{num_counter}. *Event Creation Updates:* To be sent to participants\n"

    update_event_draft(user_id, event_details)

    print(f"########### Event draft: {text_reply}", flush=True)
    return text_reply
        
def confirm_event_draft(user_id):
    index, memory = get_user_memory(user_id)
    if memory:
        session_memories[index]['latest_event_draft']['status'] = 'confirmed'
        return True
    else:
        return False
    
def save_event_to_calendar(instruction, user_id, is_test=False):
    service = get_calendar_service(user_id, is_test)

    try:
        json_str = instruction.split('add_event:')[1].strip()
        print(f"####### JSON string: {json_str}")
        event_details = json.loads(json_str)
        update_event_draft(user_id, event_details)
    except Exception as e:
        print(f"####### Failed to parse event JSON: {e}")
        return "Sorry, I couldn't understand your event details."

    name = event_details['name']
    start_date_str = event_details['start_date']
    end_date_str = event_details['end_date']
    start_date = datetime.fromisoformat(start_date_str)
    end_date = (start_date + timedelta(hours=1)) if end_date_str is None else datetime.fromisoformat(end_date_str)
    timezone = event_details.get('timezone', None)
    location = event_details['location']
    description = event_details['description']
    participants = event_details['participants']
    reminder_minutes = event_details['reminder']
    calendar_name = event_details.get('calendar', 'primary')
    sendUpdates = event_details.get('send_updates', False)
    calendar_id = 'primary'

    sendUpdates = 'all' if (sendUpdates or sendUpdates == 'true') else 'none'

    print('CALENDAR NAME: ', calendar_name)
    if calendar_name != 'primary':
        calendars = list_calendars(service)
        calendar_id = None
        for calendar in calendars['items']:
            if str(calendar['summary']).lower() == str(calendar_name).lower():
                calendar_id = calendar['id']
                break
        if not calendar_id:
            print(f"########### Calendar '{calendar_name}' not found.")
            return "Sorry, I can not find the specific calendar name you're referring to."
        
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
            'dateTime': start_date.isoformat()
        },
        'end': {
            'dateTime': end_date.isoformat()
        },
        'attendees': attendees,
        'reminders': reminder,
        "visibility": "default",
    }

    if timezone:
        event['start']['timeZone'] = timezone
        event['end']['timeZone'] = timezone

    print(f"########### FINAL event details: {event}", flush=True)
    try:
        if sendUpdates == 'all':
            new_event = service.events().insert(calendarId=calendar_id, body=event, sendUpdates=sendUpdates).execute()
        else:
            new_event = service.events().insert(calendarId=calendar_id, body=event).execute()

        confirm_event_draft(user_id)
        return f"Event {new_event.get('summary', '')} created: {new_event.get('htmlLink')}"
    except Exception as e:
        print(f"########### Error adding to g-cal: {str(e)}")
        return None
    

    
