from datetime import datetime, timedelta, timezone
import re
import requests
import base64
from requests.auth import HTTPBasicAuth
import re
from creds import *
import pytz
from twilio.rest import Client as TwilioClient
import time

def clean_instruction_block(instruction):
    # remove backticks and "```json" if present
    instruction = instruction.replace("```json", "").replace("```", "").strip()
    return instruction

def readable_date(date_str, is_datetime=None, with_timezone=True):
    try:
        date = datetime.fromisoformat(date_str)

        if is_datetime:
            transformed = date.strftime("%A, %d %B %Y %H:%M %Z") if with_timezone else date.strftime("%A, %d %B %Y %H:%M")
        else:
            transformed = date.strftime("%A, %d %B %Y")

        return transformed
    except ValueError:
        return date_str
    
def clean_description(text):
    cleaned = re.sub(r'<.*?>', '', text)
    return cleaned.strip()

def extract_phone_number(user_id):
    print(f"########### Extracting phone number from user_id: {user_id}", flush=True)
    phone_number = re.findall(r'\d+', user_id)
    if phone_number and len(phone_number) > 0:
        return phone_number[0]
    else:
        raise ValueError("Invalid user ID format. Phone number not found.")
    
def get_image_data_url(media_url, content_type):
    try:
        response = requests.get(media_url, auth=HTTPBasicAuth(TWILIO_SID, TWILIO_AUTH_TOKEN))
        image_data = base64.b64encode(response.content).decode('utf-8')
        image_data_url = f"data:{content_type};base64,{image_data}"
        return image_data_url
    except Exception as e:
        raise Exception("Error fetching media: {e}")
    
def split_message(text, max_length=1530):
    return [text[i:i+max_length] for i in range(0, len(text), max_length)]

# def get_timezone_from_phone(phone_number):
#     try:
#         parsed = phonenumbers.parse(phone_number)
#         timezones = timezone.time_zones_for_number(parsed)
#         return timezones  # This returns a list, e.g., ['Asia/Jakarta']
#     except:
#         return None
    
def convert_timezone(time_str, target_tz='Asia/Jakarta'):
    try:
        dt = datetime.fromisoformat(time_str)
        target_tz = pytz.timezone(target_tz)
        dt_converted = dt.astimezone(target_tz)
        return dt_converted.isoformat()
    except Exception as e:
        print(f"Error converting timezone: {e}")
        return None

def send_whatsapp_message(to, message):
    print(f"########### Sending WhatsApp message from: {TWILIO_PHONE_NUMBER_SANDBOX} to {to}: {message}", flush=True)
    try: 
        client = TwilioClient(TWILIO_SID, TWILIO_AUTH_TOKEN)
        client.messages.create(
            from_=TWILIO_PHONE_NUMBER_SANDBOX,
            to=to,
            body=message
        )
        print(f"########### WhatsApp message sent successfully", flush=True)
        time.sleep(0.5)
    except Exception as e:
        print(f"########### Error sending WhatsApp message: {e}", flush=True)
        raise Exception("Error sending WhatsApp message")

EMAIL_REGEX = re.compile(r"^[^@]+@[^@]+\.[^@]+$")

def all_valid_emails(email_list):
    print(f"########### Checking email validity: {email_list}", flush=True)
    return all(EMAIL_REGEX.match(email) for email in email_list)
    