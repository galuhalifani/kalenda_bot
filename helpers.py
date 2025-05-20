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
import uuid

def trim_reply(reply_text):
    max_length=1400
    split = [reply_text[i:i+max_length] for i in range(0, len(reply_text), max_length)]
    trimmed_reply = split[0]
    reply_text = f"Your list is too long, I can only show partial results. For more complete list, please specify a shorter date range.\n\n {trimmed_reply}"
    return reply_text

def clean_instruction_block(instruction):
    instruction = instruction.replace("```json", "").replace("```", "").strip()
    return instruction

def readable_date(date_str, is_datetime=None, with_timezone=True):
    try:
        date = datetime.fromisoformat(date_str)

        if is_datetime:
            transformed = date.strftime("%a, %d %b %Y %H:%M %Z") if with_timezone else date.strftime("%a, %d %b %Y %H:%M")
        else:
            transformed = date.strftime("%a, %d %b %Y")

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
        allowed_types = {"image/png", "image/jpeg", "image/gif", "image/webp"}
        if content_type not in allowed_types:
            print(f"❌ Unsupported image type: {content_type}")
            return "Only PNG, JPEG, GIF, or WEBP image formats are supported."
        
        response = requests.get(media_url, auth=HTTPBasicAuth(TWILIO_SID, TWILIO_AUTH_TOKEN))
        image_data = base64.b64encode(response.content).decode('utf-8')
        image_data_url = f"data:{content_type};base64,{image_data}"
        return image_data_url
    except Exception as e:
        raise Exception(f"Error fetching media: {e}")

def get_voice_data_url(media_url, content_type, user_id):
    response = requests.get(media_url, auth=HTTPBasicAuth(TWILIO_SID, TWILIO_AUTH_TOKEN))
    if not response.headers["Content-Type"].startswith("audio/"):
        print("❌ Response Content-Type not audio:", response.headers["Content-Type"])
        return "Invalid audio file."
    contentType = content_type.split("/")[-1]
    filename = f"{user_id}_{uuid.uuid4().hex}.{contentType}"  # e.g., input.ogg, input.m4a
    with open(filename, "wb") as f:
        f.write(response.content)
    return filename

def transcribe_audio(voice_data_filename, client):
    print(f"########### Transcribing audio file: {voice_data_filename}", flush=True)
    with open(voice_data_filename, "rb") as audio_file:
        transcript = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            response_format="text"
        )

    print(f"########### Transcription result: {transcript}", flush=True)
    return transcript
    
def split_message(text, max_length=1530):
    return [text[i:i+max_length] for i in range(0, len(text), max_length)]
    
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
    twilio_number = TWILIO_PHONE_NUMBER if mode == 'production' else TWILIO_PHONE_NUMBER_SANDBOX
    print(f"########### Sending WhatsApp message from: {twilio_number} to {to}: {message}", flush=True)
    try: 
        client = TwilioClient(TWILIO_SID, TWILIO_AUTH_TOKEN)
        client.messages.create(
            from_=twilio_number,
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

def extract_emails(args):
    cleaned = args[1].strip()
    if cleaned:
        match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', cleaned)
        if match:
            user_email = match.group(0)
            print(f"########### User email: {user_email}", flush=True)
            return user_email
        else:
            print("########### No email found in the text", flush=True)
            return None
        
def extract_json_block(text):
    start_index = text.find('{')
    if start_index == -1:
        return None

    brace_count = 0
    for i in range(start_index, len(text)):
        if text[i] == '{':
            brace_count += 1
        elif text[i] == '}':
            brace_count -= 1
            if brace_count == 0:
                return text[start_index:i+1]
            
    return None