def summarize_event(resp, user_id, input, is_test=False, image_data_url=None, voice_data_filename=None):
    cal_timezone = get_user_calendar_timezone(user_id, is_test)
    user_timezone = check_timezone(user_id, cal_timezone)
    raw_answer = init_llm(user_id, input, 'main', image_data_url, user_timezone, voice_data_filename, None)
    answer = clean_instruction_block(raw_answer)
    is_answer_string = isinstance(answer, str)
    whatsappNum = f'whatsapp:+{user_id}'

    if is_answer_string and 'add_event:' in answer.strip():
        print(f"########### Adding event: {answer}", flush=True)
        try:
            loading_message = "Adding your event..."
            send_whatsapp_message(f'{whatsappNum}', loading_message)
        except Exception as e:
            print(f"########### Error sending loading message: {str(e)}", flush=True)

        try:
            new_event = save_event_to_calendar(answer, user_id, is_test)
            print(f"########### Replying event: {new_event}", flush=True)
            return new_event
        except Exception as e:
            print(f"########### Error adding new event: {e}", flush=True)
            return "Sorry, I could not add the event to your calendar."

    elif is_answer_string and 'draft_event:' in answer.strip():
        print(f"########### Drafting event: {answer}", flush=True)
        try:
            loading_message = "Drafting..."
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
        
    elif is_answer_string and 'retrieve_event:' in answer.strip():
        print(f"########### Retrieving events: {answer}", flush=True)
        try:
            loading_message = "Fetching your events..."
            send_whatsapp_message(f'{whatsappNum}', loading_message)
        except Exception as e:
            print(f"########### Error sending loading message: {str(e)}", flush=True)
        try:
            events = get_upcoming_events(answer, user_id, is_test)
            print(f"########### All list of Events: {events}", flush=True)
            event_list, _, _, action = events
            if action == 'retrieve':
                user_events = transform_events_to_text(events, user_timezone)
                return user_events
            elif action == 'retrieve_free_time':
                raw_answer_analyzer = init_llm(user_id, input, 'schedule_analyzer', image_data_url, user_timezone, voice_data_filename, event_list)
                return raw_answer_analyzer
        except Exception as e:
            print(f"########### Error retrieving events: {str(e)}", flush=True)
            return "Sorry, I am unable to fetch your events at the moment."

    elif is_answer_string and 'timezone_set:' in answer.strip():
        print(f"########### Setting timezone: {answer}", flush=True)
        try:
            new_timezone_raw = answer.split('timezone_set: ')[1].strip()
            new_timezone = extract_json_block(new_timezone_raw)
            updated_timezone = add_update_timezone(user_id, new_timezone)
            if updated_timezone:
                return f'Your timezone has been changed to {new_timezone}. Please proceed with your request.'
            else:
                return f'Failed to set your timezone. Please try again.'
        except Exception as e:
            print(f"########### Error updating timezone: {str(e)}", flush=True)
            return "Sorry, I could not set your timezone. Please try again."
        
    elif is_answer_string and answer.strip().startswith("Event not added"):
        print(f"########### Event not added: {answer}", flush=True)
        return "Sorry, I'm unable to assist you with this event. Please start over with more details."
    
    else:
        print(f"########### Instruction not recognized: {answer}", flush=True)
        return answer