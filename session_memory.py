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

def add_user_memory(user_id, input, answer):
    print(f"########### Adding memory for user: {user_id}", flush=True)
    try:
        global session_memories
        print(f"########### All memories: {session_memories}", flush=True)
        index, memory = get_user_memory(user_id)
        if memory:
            print(f"########### Memory found: {memory}", flush=True)

            if 'latest_conversations' not in memory:
                session_memories[index]['latest_conversations'] = []
            else:
                print(f"########### Latest Conversation found. latest conv: {memory['latest_conversations']}", flush=True)
                if len(memory['latest_conversations']) > max_chat_stored:
                    session_memories[index]['latest_conversations'].pop(0)

            session_memories[index]['latest_conversations'].append({
                "userMessage": input,
                "aiMessage": answer,
                "timestamp": datetime.now(tzn.utc)
            })
            print(f"########### Memory appended: {session_memories[index]}", flush=True)
        else:
            session_memories.append({
                "user_id": user_id,
                "latest_conversations": [{
                    "userMessage": input,
                    "aiMessage": answer,
                    "timestamp": datetime.now(tzn.utc)
                }],
                "latest_event_draft": {}
            })
    except Exception as e:
        print(f"########### Error adding memory: {e}", flush=True)

def get_user_memory(user_id):
    for index, memory in enumerate(session_memories):
        if memory['user_id'] == user_id:
            print(f"########### Memory found: {memory}", flush=True)
            return index, memory
    print(f"########### No memory found for user: {user_id}", flush=True)
    return None, None

def delete_user_memory(user_id):
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

def get_latest_memory(user_id):
    for memory in session_memories:
        _, memory = get_user_memory(user_id)
        if memory:
            latest_draft = memory['latest_event_draft'] if memory['latest_event_draft'] else None
            latest_draft_status = latest_draft['status'] if latest_draft else None
            user_latest_event_draft = latest_draft if latest_draft_status == 'draft' else None
            print(f"########### User latest event draft: {user_latest_event_draft}", flush=True)
            latest_conversations = memory['latest_conversations'] if memory['latest_conversations'] else None
            print(f"########### User latest conversations: {latest_conversations}", flush=True)
            return latest_conversations, user_latest_event_draft
    print(f"########### No memory found for user: {user_id}", flush=True)
    return None, None