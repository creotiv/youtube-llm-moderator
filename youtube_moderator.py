import os
import time
import pickle
import requests  # For requests to the LM Studio API
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# --- CONFIGURATIONS ---
CLIENT_SECRET_FILE = 'client_secret.json'  # Path to your client_secret.json
LMSTUDIO_API_URL = 'http://localhost:1234/v1/chat/completions'  # URL of your LM Studio server
# Replace 'your-loaded-model-identifier' with the identifier of the model you have loaded and running in LM Studio
# For example: 'lmstudio-community/Phi-3-mini-4k-instruct-GGUF/Phi-3-mini-4k-instruct-Q4_K_M.gguf'
LLM_MODEL_NAME = 'google/gemma-3-12b'
# System prompt for LLM. Customize it for better detection of "bad" comments.
LLM_SYSTEM_PROMPT = """
You are an AI YouTube chat moderator for a Ukrainian/Russian language channel. Your primary goal is to maintain a respectful and engaging live chat environment while minimizing censorship of legitimate discussion. Focus on identifying content that actively harms the community, not policing opinions.

Respond with:

DELETE – only if the comment:
* directly insults or threatens an individual.
* explicitly supports Russian military aggression or war crimes.
* uses "Russia" with a capital letter (in any language) unless referring to geographical location.
* uses "Ukraine" with a lowercase letter (in any language) when referring to the country.
* contains hate speech or discriminatory remarks based on ethnicity, religion, gender, etc.

KEEP – for all other messages, including:
* Discussions about politics or current events (unless hateful).
* General conversation and greetings.
* Questions related to the video content.

Important Guidelines:
* When in Doubt, DELETE. Prioritize user safety and a positive community experience.
"""
POLL_INTERVAL_SECONDS = 10  # How often to check for new messages (in seconds)
REQUIRED_SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]  # Required for deleting messages
TOKEN_PICKLE_FILE = 'token.pickle'  # File for saving authorization tokens

# Variable to store IDs of already processed messages to avoid re-checking them
processed_message_ids = set()
last_poll_time = None


def authenticate_youtube():
    """Authenticate via OAuth 2.0 and get the YouTube API service."""
    creds = None
    if os.path.exists(TOKEN_PICKLE_FILE):
        with open(TOKEN_PICKLE_FILE, 'rb') as token:
            creds = pickle.load(token)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, REQUIRED_SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_PICKLE_FILE, 'wb') as token:
            pickle.dump(creds, token)

    return build('youtube', 'v3', credentials=creds)


def get_active_live_chat_id(youtube):
    """Finds the user's active stream and returns its chat ID."""
    try:
        print("🔍 Searching for user broadcasts...")
        request = youtube.liveBroadcasts().list(
            part="snippet,contentDetails,status",
            mine=True  # Request all user broadcasts
        )
        response = request.execute()

        if not response.get('items'):
            print("😕 No user broadcasts found.")
            return None

        active_broadcast = None
        for broadcast_item in response.get('items', []):
            # Check broadcast status to find the active one
            # 'live' status means the broadcast is currently live
            # Can also check broadcast_item['status']['recordingStatus'] == 'recording'
            if broadcast_item.get('status', {}).get('lifeCycleStatus') == 'live':
                active_broadcast = broadcast_item
                break  # Found an active broadcast

        if not active_broadcast:
            print("😕 No active streams found among user broadcasts.")
            return None

        live_chat_id = active_broadcast['snippet']['liveChatId']
        stream_title = active_broadcast['snippet']['title']
        print(f"🟢 Active stream found: '{stream_title}' (Live Chat ID: {live_chat_id})")
        return live_chat_id
    except HttpError as e:
        print(f"YouTube API error while searching for active stream: {e}")
        # Add error details if available
        if e.error_details:
            for detail in e.error_details:
                print(f"  - {detail['reason']}: {detail['message']}")
        return None
    except Exception as e:
        print(f"Unknown error while searching for active stream: {e}")
        return None


def get_live_chat_messages(youtube, live_chat_id, page_token=None):
    """Retrieves new messages from the chat."""
    global last_poll_time
    try:
        request = youtube.liveChatMessages().list(
            liveChatId=live_chat_id,
            part="snippet,authorDetails,id",
            maxResults=200,  # Maximum number of messages per request
            pageToken=page_token
        )
        response = request.execute()
        return response
    except HttpError as e:
        if e.resp.status == 403 and 'disabled' in str(e).lower():
            print(f"🔴 Error: Chat for this stream is disabled or unavailable. ({e})")
            return None
        print(f"YouTube API error while retrieving messages: {e}")
        return None
    except Exception as e:
        print(f"Unknown error while retrieving messages: {e}")
        return None


def moderate_message_with_llm(message_text):
    """Sends a message to the local LLM for moderation."""
    if not message_text:
        return "KEEP"  # Empty messages are considered safe

    payload = {
        "model": LLM_MODEL_NAME,
        "messages": [
            {"role": "system", "content": LLM_SYSTEM_PROMPT},
            {"role": "user", "content": message_text}
        ],
        "temperature": 0.1,  # Low temperature for more deterministic responses
        "max_tokens": 10  # "DELETE" or "KEEP" - short responses
    }
    try:
        response = requests.post(LMSTUDIO_API_URL, json=payload, timeout=30)  # timeout 30 seconds
        response.raise_for_status()  # Check for HTTP errors
        llm_response = response.json()
        decision = llm_response['choices'][0]['message']['content'].strip().upper()
        print(f"🤖 LLM ({LLM_MODEL_NAME}) decided: '{decision}' for message: '{message_text}'")
        if decision not in ["DELETE", "KEEP"]:
            print(f"⚠️ Unexpected response from LLM: '{decision}'. Defaulting to 'KEEP'.")
            return "KEEP"
        return decision
    except requests.exceptions.RequestException as e:
        print(f"Connection error with LM Studio API: {e}")
        return "KEEP"  # If LLM is unavailable, do not delete the message
    except KeyError:
        print(f"Error: Invalid response format from LLM: {llm_response}")
        return "KEEP"
    except Exception as e:
        print(f"Unknown error interacting with LLM: {e}")
        return "KEEP"


def delete_chat_message(youtube, message_id):
    """Deletes a message from YouTube chat."""
    try:
        youtube.liveChatMessages().delete(id=message_id).execute()
        print(f"🗑️ Message {message_id} successfully deleted.")
    except HttpError as e:
        print(f"YouTube API error when deleting message {message_id}: {e}")
    except Exception as e:
        print(f"Unknown error when deleting message {message_id}: {e}")


def main():
    """Main function of the script."""
    global processed_message_ids
    global last_poll_time

    print("🚀 Starting YouTube Chat Moderator Bot...")
    if LLM_MODEL_NAME == 'your-loaded-model-identifier':
        print("🚨 IMPORTANT: Please set the correct `LLM_MODEL_NAME` in the script configurations!")
        return

    youtube = authenticate_youtube()
    if not youtube:
        print("Authentication failed. Exiting.")
        return

    live_chat_id = None
    next_page_token = None

    try:
        while True:
            if not live_chat_id:
                live_chat_id = get_active_live_chat_id(youtube)
                if not live_chat_id:
                    print(f"No active streams found. Retrying in {POLL_INTERVAL_SECONDS * 5} seconds...")
                    time.sleep(POLL_INTERVAL_SECONDS * 5)
                    continue
                else:
                    # Reset processed messages and page token for a new stream/chat
                    processed_message_ids = set()
                    next_page_token = None
                    print(f"🎧 Starting to monitor chat ID: {live_chat_id}")

            chat_response = get_live_chat_messages(youtube, live_chat_id, page_token=next_page_token)

            if chat_response:
                new_messages_count = 0
                for item in chat_response.get('items', []):
                    message_id = item['id']
                    if message_id not in processed_message_ids:
                        new_messages_count += 1
                        processed_message_ids.add(message_id)
                        author_name = item['authorDetails']['displayName']
                        message_text = item['snippet']['displayMessage']
                        print(f"\n💬 New message from {author_name}: {message_text}")

                        moderation_decision = moderate_message_with_llm(message_text)

                        if moderation_decision == "DELETE":
                            print(f"🚫 Inappropriate message detected. Deleting...")
                            delete_chat_message(youtube, message_id)
                        else:
                            print("✅ Message is acceptable.")

                if new_messages_count == 0:
                    print(f".", end="", flush=True)

                next_page_token = chat_response.get('nextPageToken')
                # Use pollingIntervalMillis if available, or our default
                poll_interval = chat_response.get('pollingIntervalMillis', POLL_INTERVAL_SECONDS * 1000) / 1000.0
                # Add a small buffer and limit the minimum interval
                actual_poll_interval = max(POLL_INTERVAL_SECONDS, poll_interval + 2)
                time.sleep(actual_poll_interval)
            elif chat_response is None and live_chat_id:  # Likely chat is disabled or stream ended
                print(f"⚠️ Failed to get messages from chat {live_chat_id}. Perhaps the stream has ended or chat is disabled.")
                print(f"🔁 Trying to find a new active stream in {POLL_INTERVAL_SECONDS * 3} seconds.")
                live_chat_id = None  # Reset ID so the script tries to find a new stream
                next_page_token = None
                processed_message_ids = set()
                time.sleep(POLL_INTERVAL_SECONDS * 3)
            else:  # If chat_response is None and live_chat_id is not set (initial state or error)
                time.sleep(POLL_INTERVAL_SECONDS)

    except KeyboardInterrupt:
        print("\n🛑 Bot stopped by user.")
    except Exception as e:
        print(f"💥 Critical error in main loop: {e}")
    finally:
        print("👋 Shutting down bot.")


if __name__ == '__main__':
    main()
