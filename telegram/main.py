import os
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
import requests

# Load environment variables

# Get your Telegram bot token and Converse API endpoint from environment variables
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CONVERSE_API_ENDPOINT = os.getenv("CONVERSE_API_ENDPOINT")
CONVERSE_API_KEY = os.getenv("CONVERSE_API_KEY")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Welcome! I can help you interact with Amazon Bedrock using Converse API. Just send me a message!"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    help_text = """
    I can help you with various tasks using Amazon Bedrock. Just send me a message, and I'll process it using the Converse API.
    
    Available tools:
    - Set Availability
    - Create Event
    - Set Event Time
    
    Example: "Set my availability to busy for the next 2 hours"
    """
    await update.message.reply_text(help_text)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_message = update.message.text

    # Prepare the payload for Converse API
    payload = {
        "messages": [{"role": "user", "content": user_message}],
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "setAvailability",
                    "description": "Set user availability status",
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "createEvent",
                    "description": "Create a new event",
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "setEventTime",
                    "description": "Set the time for an existing event",
                },
            },
        ],
    }

    # Make a request to Converse API
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {CONVERSE_API_KEY}",
    }

    response = requests.post(CONVERSE_API_ENDPOINT, json=payload, headers=headers)

    if response.status_code == 200:
        api_response = response.json()
        # Extract the assistant's message from the API response
        assistant_message = api_response["messages"][-1]["content"]
        await update.message.reply_text(assistant_message)
    else:
        await update.message.reply_text(
            "Sorry, I encountered an error while processing your request. Please try again later."
        )


def main() -> None:
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )

    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
