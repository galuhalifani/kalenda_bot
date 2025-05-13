# def prompt_timezone(user_input):
#     PROMPT = f'''
#     You are a timezone assistant. Your task is to ask user their timezone and return the timezone in a standard timezone format (e.g., "America/New_York" or "Asia/Jakarta").
#     If user inputs something not related to timezone, you will respond with "You have not set your timezone yet. Please provide your timezone."
    
#     If user provided something related to timezone but you are unable to interpret the timezone in user's language, you will respond with "Timezone not recognized, please try again".

#     Question: {user_input}
#     Answer:
#     '''
#     return PROMPT
    
# def init_timezone(user_input):
#     user_timezone = check_timezone(user_input)
#     if user_timezone:
#         return user_timezone
#     else:
#         prompt_timezone = prompt_timezone(user_input)
#         openai.api_key = OPENAI_KEY
#         llm_timezone = openai.chatCompletion.create(
#             model="gpt-3.5-turbo",
#             messages=[{
#                 'role': 'user',
#                 'content': [
#                     {
#                         "type": "text",
#                         "text": prompt_timezone
#                     }
#                 ]
#             }],
#             temperature=0,
#             max_tokens=500
#         )
#         print(f'####### timezone: {llm_timezone}')
#         response = llm_timezone['choices'][0]['message']['content']
#         return response