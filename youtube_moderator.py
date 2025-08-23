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
CLIENT_SECRET_FILE = "client_secret.json"  # Path to your client_secret.json
LMSTUDIO_API_URL = (
    "http://localhost:1234/v1/chat/completions"  # URL of your LM Studio server
)
# Replace 'your-loaded-model-identifier' with the identifier of the model you have loaded and running in LM Studio
# For example: 'lmstudio-community/Phi-3-mini-4k-instruct-GGUF/Phi-3-mini-4k-instruct-Q4_K_M.gguf'
LLM_MODEL_NAME = "google/gemma-3-12b"
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

Respond only with KEEP or DELETE and nothing else.
"""
POLL_INTERVAL_SECONDS = 10  # How often to run loop
REQUIRED_SCOPES = [
    "https://www.googleapis.com/auth/youtube.force-ssl"
]  # Required for deleting messages
TOKEN_PICKLE_FILE = "token.pickle"  # File for saving authorization tokens
# Advertising / promo message configuration

MODERATION_INTERVAL_SECONDS = 10

AD_MESSAGE_INTERVAL_SECONDS = 250  # Post promo message once every 3 minutes
# AD_MESSAGE_TEXT = """Друзья! Поддержите канал: подписка, лайк и колокольчик помогут распространению правды.
# А ваше спонсорство поможет увеличеть мою мотивацию делать больше стримов 🚀"""
AD_MESSAGE_TEXT = """Please support animals of Ukraine https://patreon.com/uah"""
FEATURE_AD_ACTIVE = True
FEATURE_MODERATOR_ACTIVE = False

# Ad break configuration
AD_BREAK_INTERVAL_SECONDS = 90  # Trigger ad break every 5 minutes (300 seconds)
FEATURE_AD_BREAK_ACTIVE = True  # Enable/disable ad break functionality

# Variable to store IDs of already processed messages to avoid re-checking them
processed_message_ids = set()
last_poll_time = None


def authenticate_youtube():
    """Authenticate via OAuth 2.0 and get the YouTube API service."""
    creds = None`   `
    if os.path.exists(TOKEN_PICKLE_FILE):
        with open(TOKEN_PICKLE_FILE, "rb") as token:
            creds = pickle.load(token)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                CLIENT_SECRET_FILE, REQUIRED_SCOPES
            )
            creds = flow.run_local_server(port=0)
        with open(TOKEN_PICKLE_FILE, "wb") as token:
            pickle.dump(creds, token)

    return build("youtube", "v3", credentials=creds)


def get_active_live_chat_id(youtube):
    """Finds the user's active stream and returns its chat ID."""
    try:
        print("🔍 Searching for user broadcasts...")
        request = youtube.liveBroadcasts().list(
            part="snippet,contentDetails,status",
            mine=True,  # Request all user broadcasts
        )
        response = request.execute()

        if not response.get("items"):
            print("😕 No user broadcasts found.")
            return None

        active_broadcast = None
        for broadcast_item in response.get("items", []):
            # Check broadcast status to find the active one
            # 'live' status means the broadcast is currently live
            # Can also check broadcast_item['status']['recordingStatus'] == 'recording'
            if broadcast_item.get("status", {}).get("lifeCycleStatus") == "live":
                active_broadcast = broadcast_item
                break  # Found an active broadcast

        if not active_broadcast:
            print("😕 No active streams found among user broadcasts.")
            return None

        live_chat_id = active_broadcast["snippet"]["liveChatId"]
        broadcast_id = active_broadcast["id"]
        stream_title = active_broadcast["snippet"]["title"]
        print(
            f"🟢 Active stream found: '{stream_title}' (Live Chat ID: {live_chat_id}, Broadcast ID: {broadcast_id})"
        )
        return live_chat_id, broadcast_id
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
            pageToken=page_token,
        )
        response = request.execute()
        return response
    except HttpError as e:
        if e.resp.status == 403 and "disabled" in str(e).lower():
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
            {"role": "user", "content": message_text},
        ],
        "temperature": 0.1,  # Low temperature for more deterministic responses
        "max_tokens": 10,  # "DELETE" or "KEEP" - short responses
    }
    try:
        response = requests.post(
            LMSTUDIO_API_URL, json=payload, timeout=30
        )  # timeout 30 seconds
        response.raise_for_status()  # Check for HTTP errors
        llm_response = response.json()
        decision = llm_response["choices"][0]["message"]["content"].strip().upper()
        print(
            f"🤖 LLM ({LLM_MODEL_NAME}) decided: '{decision}' for message: '{message_text}'"
        )
        if decision not in ["DELETE", "KEEP"]:
            print(
                f"⚠️ Unexpected response from LLM: '{decision}'. Defaulting to 'KEEP'."
            )
            return "DELETE"
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


def post_advertising_message(youtube, live_chat_id, message_text=AD_MESSAGE_TEXT):
    """Posts an advertising/promo message to the live chat."""
    try:
        body = {
            "snippet": {
                "liveChatId": live_chat_id,
                "type": "textMessageEvent",
                "textMessageDetails": {"messageText": message_text},
            }
        }
        youtube.liveChatMessages().insert(part="snippet", body=body).execute()
        print("📣 Posted promotional message to chat.")
        return True
    except HttpError as e:
        print(f"YouTube API error when posting promo message: {e}")
        return False
    except Exception as e:
        print(f"Unknown error when posting promo message: {e}")
        return False


def trigger_ad_break(youtube, broadcast_id, duration_secs=30):
    """
    Insert an ad cuepoint into an active live broadcast.

    Args:
        youtube: an authorized youtube API client (scopes must include
                 https://www.googleapis.com/auth/youtube or youtube.force-ssl)
        broadcast_id: the liveBroadcast id currently streaming
        duration_secs: ad break duration in seconds (default 30)
    """
    body = {"cueType": "cueTypeAd", "durationSecs": int(duration_secs)}

    try:
        print(body)
        result = (
            youtube.liveBroadcasts()
            .insertCuepoint(
                id=broadcast_id, body=body, part="snippet,contentDetails,status"
            )
            .execute()
        )
        print(result)
        print("📺 Ad cuepoint inserted.")
        return True
    except HttpError as e:
        print(f"YouTube API error when triggering ad break: {e}")
        return False
    except Exception as e:
        print(f"Unknown error when triggering ad break: {e}")
        return False


def main():
    """Main function of the script."""
    global processed_message_ids
    global last_poll_time

    print("🚀 Starting YouTube Chat Moderator Bot...")
    if LLM_MODEL_NAME == "your-loaded-model-identifier":
        print(
            "🚨 IMPORTANT: Please set the correct `LLM_MODEL_NAME` in the script configurations!"
        )
        return

    youtube = authenticate_youtube()
    if not youtube:
        print("Authentication failed. Exiting.")
        return

    live_chat_id = None
    broadcast_id = None
    next_page_token = None
    last_ad_post_time = None
    last_moderation_time = None
    last_ad_break_time = None
    total_errors = 0

    try:
        while True:
            if not live_chat_id:
                result = get_active_live_chat_id(youtube)
                if not result:
                    print(
                        f"No active streams found. Retrying in {POLL_INTERVAL_SECONDS * 5} seconds..."
                    )
                    time.sleep(POLL_INTERVAL_SECONDS * 5)
                    continue
                else:
                    live_chat_id, broadcast_id = result
                    # Reset processed messages and page token for a new stream/chat
                    processed_message_ids = set()
                    next_page_token = None
                    last_ad_post_time = time.time()  # start interval for promo posting
                    last_ad_break_time = 0  # start interval for ad breaks
                    print(f"🎧 Starting to monitor chat ID: {live_chat_id}")

            now = time.time()

            if FEATURE_AD_ACTIVE:
                if (
                    live_chat_id
                    and last_ad_post_time is not None
                    and (now - last_ad_post_time) >= AD_MESSAGE_INTERVAL_SECONDS
                ):
                    result = post_advertising_message(youtube, live_chat_id)
                    if result:
                        last_ad_post_time = now
                        total_errors = 0
                    else:
                        total_errors += 1
                        print("🚨 Failed to post advertising message.")

            if FEATURE_AD_BREAK_ACTIVE:
                if (
                    broadcast_id
                    and last_ad_break_time is not None
                    and (now - last_ad_break_time) >= AD_BREAK_INTERVAL_SECONDS
                ):
                    result = trigger_ad_break(youtube, broadcast_id)
                    if result:
                        last_ad_break_time = now
                        total_errors = 0
                    else:
                        total_errors += 1
                        print("🚨 Failed to trigger ad break.")

            if FEATURE_MODERATOR_ACTIVE:
                chat_response = None
                if (
                    live_chat_id
                    and last_moderation_time is not None
                    and (now - last_moderation_time) >= MODERATION_INTERVAL_SECONDS
                ):
                    chat_response = get_live_chat_messages(
                        youtube, live_chat_id, page_token=next_page_token
                    )
                    last_moderation_time = now
                    if not chat_response:
                        total_errors += 1

                if chat_response:
                    total_errors = 0
                    new_messages_count = 0
                    for item in chat_response.get("items", []):
                        message_id = item["id"]
                        if message_id not in processed_message_ids:
                            new_messages_count += 1
                            processed_message_ids.add(message_id)
                            author_name = ""
                            message_text = ""
                            try:
                                author_name = item["authorDetails"]["displayName"]
                                message_text = item["snippet"]["displayMessage"]
                            except:
                                print("Error getting message: ", item)
                                continue
                            print(
                                f"\n💬 New message from {author_name}: {message_text}"
                            )

                            moderation_decision = moderate_message_with_llm(
                                message_text
                            )

                            if moderation_decision == "DELETE":
                                print(f"🚫 Inappropriate message detected. Deleting...")
                                delete_chat_message(youtube, message_id)
                            else:
                                print("✅ Message is acceptable.")

                    if new_messages_count == 0:
                        print(f".", end="", flush=True)

                    next_page_token = chat_response.get("nextPageToken")

            if total_errors > 5:
                print(f"⚠️ Perhaps the stream has ended or chat is disabled.")
                print(
                    f"🔁 Trying to find a new active stream in {POLL_INTERVAL_SECONDS * 3} seconds."
                )
                live_chat_id = None  # Reset ID so the script tries to find a new stream
                broadcast_id = None
                next_page_token = None
                processed_message_ids = set()
                last_ad_post_time = None
                last_moderation_time = None
                last_ad_break_time = None
                time.sleep(POLL_INTERVAL_SECONDS * 3)
            else:
                time.sleep(POLL_INTERVAL_SECONDS)

    except KeyboardInterrupt:
        print("\n🛑 Bot stopped by user.")
    except Exception as e:
        print(f"💥 Critical error in main loop: {e}")
    finally:
        print("👋 Shutting down bot.")


if __name__ == "__main__":
    main()
