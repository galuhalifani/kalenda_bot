from pymongo import MongoClient
from creds import *
from datetime import datetime, timedelta, timezone as tzn

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
    email_collection = db['email']
    pending_auth_collection = db['pending_auth']
    pending_auth_collection.create_index("created_at", expireAfterSeconds=900)
else:
    user_collection = None
    tokens_collection = None
    email_collection = None
    pending_auth_collection = None

def check_user(user_id):
    print(f"########### Checking user: {user_id}", flush=True)
    daily_limit = 10
    user = user_collection.find_one({"user_id": user_id})
    if user:
        last_chat = user.get("last_chat", datetime.now(tzn.utc))
        balance = user.get("chat_balance", daily_limit)
        userType = user.get("type", 'regular')
        is_using_test_account = user.get("is_using_test_account", True)

        if last_chat.tzinfo is None:
            last_chat = last_chat.replace(tzinfo=tzn.utc)
        
        print(f'########## checkin user: {user_id}, last chat: {last_chat}, balance: {balance}')

        time_since_last_chat = last_chat - datetime.now(tzn.utc)
        print(f'########## time_since_last_chat: {time_since_last_chat}')

        if time_since_last_chat > timedelta(days=1) :
            # restore balance
            print("########## restoring balance")
            balance = daily_limit
            user_collection.update_one({"user_id": user_id}, {"$set": {"chat_balance": daily_limit}})

        return {"status": "existing", "user_id": user_id, "chat_balance": balance, "type": userType, "user_details": user, "is_using_test_account": is_using_test_account}
    else:
        user_collection.insert_one({"user_id": user_id, "timestamp": datetime.now(tzn.utc).isoformat(), "chat_balance": daily_limit, "type": "regular", "is_using_test_account": True})
        print(f'########## creating new user: {user_id}, balance: {daily_limit}')
        return {"status": "new", "user_id": user_id, "user_details": user, "chat_balance": daily_limit, "type": "regular", "is_using_test_account": True}

def deduct_chat_balance(user, user_id):
    try:
        if user:
            print(f'########## deduct_chat_balance: {user}, type: {user["type"]}, balance: {user["chat_balance"]}')
            if user["type"] == 'regular' and user["chat_balance"] > 0:
                user_collection.update_one(
                    {"user_id": user_id},
                    {
                        "$inc": {"chat_balance": -1},
                        "$set": {"last_chat": datetime.now(tzn.utc)}
                    }
                )
                print(f"########### Balance deducted", flush=True)
                return True
        else:
            print(f"########### User not found: {user_id}", flush=True)
            return False
    except Exception as e:
        print(f"####### Error deducting chat balance: {str(e)}")
        return False

def check_user_balance(user):
    balance = user["chat_balance"]
    print(f'########## check_user_balance: {user}, type: {user["type"]}, balance: {balance}')
    if user["type"] == 'regular' and balance > 0:
        return True
    elif user["type"] == 'unlimited':
        return True
    else:
        return False
    
def check_timezone(user_id, cal_timezone=None):
    print(f"########### Checking timezone for user: {user_id}", flush=True)
    user = user_collection.find_one({"user_id": user_id})
    
    if user:
        is_using_test_account = user.get("is_using_test_account", False)
        if is_using_test_account:
            return "Asia/Jakarta"
        
        timezone = user.get("timezone")
        if timezone:
            return timezone
        elif cal_timezone:
            return cal_timezone
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

    user_collection.update_one(
        {"user_id": user_id},
        {"$set": {
            "timezone": "Asia/Jakarta",
            "is_using_test_account": True
        }},
    upsert=True)

def check_user_active_email(user_id, user_email=None):
    print(f"########### Checking if user is whitelisted: {user_id}", flush=True)
    user = user_collection.find_one({"user_id": user_id})

    if user:
        db_email = user.get("email", None)
        email_whitelist_status = user.get("is_email_whitelisted", False)
        is_email_whitelisted = bool(email_whitelist_status == True)

        if db_email == None:
            print(f"########## User {user_id} has no whitelisted email in database", flush=True)
            return False
        else:   
            if user_email == None:     
                if is_email_whitelisted == True:
                    print(f"########### User has email in database: {db_email}", flush=True)
                    return db_email
                else:
                    return False
            else:
                email = email_collection.find_one({"email": user_email})
                if email:
                    if (email.get("is_whitelisted", False) == True):
                        print(f"########### Email is whitelisted: {user_email}", flush=True)
                        return email

                user_and_email = bool(bool(user_email == db_email) and is_email_whitelisted)
                if user_and_email:
                    return user_email # email is already whitelisted
        
    return False

def add_user_whitelist_status(user_id, email):
    try:
        print(f"########### Adding user whitelist status: email: {email}", flush=True)
        email_collection.update_one(
            {"email": email},
            {"$set": {"user_id": user_id, "is_whitelisted": "Pending"}},
            upsert=True
        )
        user_collection.update_one(
            {"user_id": user_id},
            {"$set": {"email": email, "is_email_whitelisted": "Pending"}},
            upsert=True
        )
        return True
    except Exception as e:
        print(f"Error updating whitelist status for {email}: {e}", flush=True)
        return False
    
def update_user_whitelist_status(email, status):
    try:
        print(f"########### Updating user whitelist status: {email}, status: {status}", flush=True)
        email_collection.update_one(
            {"email": email},
            {"$set": {"is_whitelisted": status}},
            upsert=True
        )
        user_collection.update_one(
            {"email": email},
            {"$set": {"is_email_whitelisted": status}},
            upsert=True
        )
        user = user_collection.find_one({"email": email})
        user_number = user.get("user_id")
        return user_number
    except Exception as e:
        print(f"Error updating whitelist status for {email}: {e}", flush=True)
        return False

def update_send_whitelisted_message_status(user_number):
    user_collection.update_one(
        {"user_id": user_number},
        {"$set": {"whitelisted_message_sent": True}},
        upsert=True
    )
    return user_number

def send_test_calendar_message(resp, using_test_calendar, user_id):
    resp.message(using_test_calendar)
    user_collection.update_one(
        {"user_id": user_id},
        {"$set": {"test_calendar_message": True}},
        upsert=True
    )

def update_send_test_calendar_message(resp, using_test_calendar, user_id):
    user = user_collection.find_one({"user_id": user_id})
    test_calendar_message = user.get("test_calendar_message", False)

    if not user or not test_calendar_message:
        sending = send_test_calendar_message(resp, using_test_calendar, user_id)
        return sending
    else:
        if test_calendar_message:
            last_chat = user.get("last_chat", datetime.now(tzn.utc))

            if last_chat.tzinfo is None:
                last_chat = last_chat.replace(tzinfo=tzn.utc)

            time_since_last_chat = last_chat - datetime.now(tzn.utc)
            print(f'########## time_since_last_chat: {time_since_last_chat}')

        if time_since_last_chat > timedelta(days=1) :
            # allow to send again
            print("########## resending test calendar message")
            user_collection.update_one({"user_id": user_id}, {"$set": {"test_calendar_message": False}})
            return False

    return test_calendar_message

def revoke_access_command(resp, user_id):
    user_email = user_collection.find_one({"user_id": user_id}).get("email", None)
    if (user_email):
        email_collection.delete_one(
            {"email": user_email})
        
        user_collection.update_one(
            {"user_id": user_id},
            {"$set": {
                "is_email_whitelisted": False,
                "whitelisted_message_sent": False,
                "test_calendar_message": True,
                "is_using_test_account": True
            },
            "$unset": {
                "email": ""
            }}
        )

        tokens_collection.delete_one(
            {"user_id": user_id}
        )
        resp.message("✅ Your access has been revoked. You can re-authenticate by typing 'authenticate'")
        return str(resp)
    else:
        resp.message("You are not connected to any email account. To connect and get whitelisted, please type 'authenticate <your-email>'")
        return str(resp)
    
def add_pending_auth(user_id, state):
    try:
        pending_auth_collection.update_one(
            {"state": state},
            {"$set": {"user_id": user_id, "created_at": datetime.now()}},
            upsert=True
        )
        return True
    except Exception as e:
        print(f"Error adding pending auth for {user_id}: {e}", flush=True)
        return False

def get_pending_auth(state):
    try:
        pending_auth = pending_auth_collection.find_one_and_delete({"state": state})
        if pending_auth:
            return pending_auth
        else:
            return None
    except Exception as e:
        print(f"Error getting pending auth for {state}: {e}", flush=True)
        return None