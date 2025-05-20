greeting = (
    "👋 Hi! Kalenda here -- I'm here to help make adding calendar event faster for you. You can view today and tomorrow's events in the calendar, as well as add new events to the calendar'\n\n"
    "To add event, you can type the event details via chat, send a voice note, or screenshot an event and forward it to me -- as simple as that!\n\n"
)

using_test_calendar = (
    "🔧 You are now using our public test calendar.\n\n"
    "If you wish to connect your own calendar, please type: \n _authenticate <your-g-cal-email>_ \n for example: _authenticate kalenda@gmail.com_. \n We will add your email to the whitelist within 24 hours.\n\n"
    "You can access and view the test calendar here:\n"
    "📅 https://calendar.google.com/calendar/embed?src=kalenda.bot%40gmail.com \n\n"
)

def connect_to_calendar(auth_link, email):
    return (
        "🔐 Click to connect your Google Calendar:\n"
        f"{auth_link}\n\n"
        f"Choose your email, then click _continue_ to connect to your account\n\n"
        f"You can only connect to the email that has been whitelisted ({email}). To connect to another calendar, type _authenticate <other-email-address>_\n\n"
        f"Please note that the link will expire in 24 hours. If you need a new link, just type _authenticate_.\n\n"
    )

def connect_to_calendar_confirmation(auth_link, email):
    return (
        f"✅ Your email {email} has been whitelisted. You can now connect your Google Calendar using the following link: \n\n{auth_link} \n\n"
        f"Choose your email, then click _continue_ to connect to your account\n\n"
        f"You can only connect to the email that has been whitelisted ({email})\n\n"
        f"The link will expire in 24 hours. To generate a new link, type _authenticate_"
    )