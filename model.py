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
from __future__ import print_function
import datetime
import os.path
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from cal import get_calendar_service, get_upcoming_events

load_dotenv(override=True)
MONGODB_URL=os.getenv('MONGO_URI')
OPENAI_KEY=os.getenv('OPENAI_KEY')

def prompt_init(question):
    PROMPT = f'''
    You are a scheduler assistant. Your main task is to help manage user's schedule.
    You will be given an instruction by the user to either add an event to the calendar or retrieve events from the calendar.

    - If user asks to add an event, you need to respond with USER FORMAT:
        1. The event name
        2. The event date and time
        3. The event location
        4. The event description
        6. The event participants
    
    Then ask the user to confirm the event details. If the user confirms, you will respond SYSTEM FORMAT:
        'add_event: {
            "name": event_name,
            "date": event_date,
            "location": event_location,
            "description": event_description,
            "participants": event_participants
        }'

    If the user doesn't confirm, you will ask user to specify the correct details, revise the event details, return the corrected USER FORMAT, and ask for confirmation again (repeat the process until user confirms).
    If after three revision attempts the user doesn't confirm, you will respond with "Event not added" and stop the process.

    - If user asks to retrieve events, you need to respond "Retrieve Events" of the today and tomorrow with format:
    'retrieve_event: today_date - tomorrow_date'
    
    Question: {question}
    Answer:
    '''
    return PROMPT

def init_llm(prompt, question):
    prompt = prompt_init(question)
    openai.api_key = OPENAI_KEY
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
                    "text": question
                }
            ]
        }],
        temperature=0
    )
    print(f'####### full response: {llm}')
    response = llm['choices'][0]['message']['content']
    return response

def summarize_event(prompt, question):
    instruction = init_llm(prompt, question)
    if 'add_event' in instruction:
        event_details = instruction.split('add_event: ')[1].split('}')[0] + '}'
        event_details = eval(event_details)
        event_name = event_details['name']
        event_date = event_details['date']
        event_location = event_details['location']
        event_description = event_details['description']
        event_participants = event_details['participants']
        return {
            'action': 'add_event',
            'event': {
                'name': event_name,
                'date': event_date,
                'location': event_location,
                'description': event_description,
                'participants': event_participants
            }
        }
    elif 'retrieve_event' in instruction:
        start_date = instruction.split('retrieve_event: ')[1].split('-')[0].strip()
        end_date = instruction.split('retrieve_event: ')[1].split('-')[1].strip()
        return {
            'action': 'retrieve_event',
            'event': {
                'start_date': start_date,
                'end_date': end_date
            }
        }


