greeting = (
    "👋 Hi! Kalenda here -- I'm here to help make adding calendar event faster for you. Please take time to read our privacy policy: kalenda.id/privacy, and our guide: kalenda.id/guide\n\n You can try typing _what do I have today_ or _what is my availability tomorrow_'\n\n"
    "Or to add a new event, just text or forward me your event via chat, via a voice note, or even screenshot -- as simple as that!\n\n"
)

using_test_calendar = (
    "🔧 You are now using our public shared test calendar.\n\n"
    "If you wish to connect your own calendar, please type: *authenticate* to enable oauth connection\n\n"
    "You can access and view the test calendar here:\n"
    "📅 https://calendar.google.com/calendar/embed?src=kalenda.bot%40gmail.com \n\n"
)

using_test_calendar_whitelist = (
    "🔧 You are now using our public test calendar.\n\n"
    "If you wish to connect your own calendar, please type: _authenticate <your-google-email>_ \n\nWe will add your email to the whitelist within 24 hours.\n\n"
    "Only personal email with a valid google account is eligible to be whitelisted\n\n"
    "You can access and view the test calendar here:\n"
    "📅 https://calendar.google.com/calendar/embed?src=kalenda.bot%40gmail.com \n\n"
)

def connect_to_calendar(auth_link, email):
    return (
        "🔐 Click to connect your Google Calendar:\n"
        f"{auth_link}\n\n"
        f"Choose your email, then click _continue_ to connect to your account\n\n"
        f"Please note that the link will expire in 24 hours. If you need a new link, just type _authenticate_.\n\n"
    )

def connect_to_calendar_whitelist(auth_link, email):
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
        f"You can only connect to the email that has been whitelisted\n\n"
        f"The link will expire in 24 hours. To generate a new link, type _authenticate_"
    )

def get_help_text():
    return (
        "*👋 Welcome to Kalenda!*\n\n"
        "*What I Can Do:*\n"
        "• Draft events from text, image, or voice note\n"
        "• Modify & add events to calendar\n"
        "• Fetch your agenda\n"
        "• Analyze your availability\n\n"
        "*What I Can't Do:*\n"
        "• Edit or delete existing events\n"
        "(Do this directly in Google Calendar)\n\n"
        "*Try saying:*\n"
        "_Doctor appointment tomorrow 10AM at RS Bunda_\n"
        "_What’s my agenda next week?_\n"
        "_What’s my availability Friday?_\n\n"
        "*Getting Started:*\n"
        "1. Use me now with public calendar\n"
        "2. Or connect to your own Google Calendar:\n"
        "   - `authenticate <your email>` then wait to get you whitelisted\n"
        "   - `authenticate` to connect to your calendar\n"
        "   - `revoke access` to revoke all access\n\n"
        "ℹ️ *Need help with shared calendar edits?*\n"
        "Email: kalenda.bot@gmail.com\n"
    )