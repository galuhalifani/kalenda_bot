from datetime import datetime, timedelta, timezone as tzn

latest_event_draft = [{
    "user_id": "id123",
    "details": {
        "name": 'test event',
        "start_date": '2025-06-12T08:15:00+07:00',
        "end_date": '2025-06-12T09:00:00+07:00',
        "location": 'Jakarta',
        "description": 'No description',
        "reminder": None,
        "participants": [],
        "status": 'draft'
    }
}]

session_memories = [{
    "user_id": "id123",
    "latest_conversations": [
        {
            "userMessage": "hello",
            "aiMessage": "hi",
            "timestamp": "2025-06-12T08:15:00+07:00"
        }
    ],
    "latest_event_draft": {
        "name": 'test event',
        "start_date": '2025-06-12T08:15:00+07:00',
        "end_date": '2025-06-12T09:00:00+07:00',
        "location": 'Jakarta',
        "description": 'No description',
        "reminder": None,
        "participants": [],
        "status": 'draft'
    }
}]

max_chat_stored = 5

def get_user_memory(user_id):
    for index, memory in enumerate(session_memories):
            if memory['user_id'] == user_id:
                print(f"########### Memory found: {memory}", flush=True)
                return index, memory
    print(f"########### No memory found for user: {user_id}", flush=True)
    return None, None

def delete_user_memory(user_id):
    print(f"########### Deleting memory for user: {user_id}", flush=True)
    _, memory = get_user_memory(user_id)

    if not memory:
        print(f"########### No memory found for user: {user_id}", flush=True)
        return

    print(f"########### Memory found. latest conv: {memory['latest_conversations']}", flush=True)

    if memory['latest_conversations']:
        last_ts = memory['latest_conversations'][-1]['timestamp']
        is_24_hours = last_ts < datetime.now(tzn.utc) - timedelta(hours=24)
        
        if is_24_hours:
            print(f"########### Memory expired for user: {user_id}", flush=True)
            global session_memories
            session_memories = [m for m in session_memories if m['user_id'] != user_id]
            print(f"########### Memory deleted for user: {user_id}", flush=True)
            return
        else:
            print(f"########### Memory still valid for user: {user_id}", flush=True)
    return