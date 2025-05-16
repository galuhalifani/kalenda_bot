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
else:
    user_collection = None
    tokens_collection = None

def check_user(user_id):
    print(f"########### Checking user: {user_id}", flush=True)
    daily_limit = 10
    user = user_collection.find_one({"user_id": user_id})
    if user:
        last_chat = user.get("last_chat", datetime.now(tzn.utc))
        balance = user.get("chat_balance", daily_limit)
        userType = user.get("type", 'regular')

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

        return {"status": "existing", "user_id": user_id, "chat_balance": balance, "type": userType, "user_details": user}
    else:
        user_collection.insert_one({"user_id": user_id, "timestamp": datetime.now(tzn.utc).isoformat(), "chat_balance": daily_limit, "type": "regular"})
        print(f'########## creating new user: {user_id}, balance: {daily_limit}')
        return {"status": "new", "user_id": user_id, "user_details": user, "chat_balance": daily_limit, "type": "regular"}

def deduct_chat_balance(user, user_id):
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