import os
import sys
import time
import pickle
import json
import requests  # For requests to the LM Studio API
import csv
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

AD_MESSAGE_INTERVAL_SECONDS = 60  # Post promo message once every 3 minutes
AD_MESSAGE_TEXT = """Друзья! Поддержите канал: подписка(c колокольчиком), лайк и донат помогут распространению правды. 
Что бы получить доступ к чату, напишите "Путин Хуйло" """
# AD_MESSAGE_TEXT = """Please support animals of Ukraine https://patreon.com/uah"""
FEATURE_AD_ACTIVE = True
FEATURE_MODERATOR_ACTIVE = "LOGIN"

# Ad break configuration
AD_BREAK_INTERVAL_SECONDS = 90  # Trigger ad break every 5 minutes (300 seconds)
FEATURE_AD_BREAK_ACTIVE = True  # Enable/disable ad break functionality
AD_BREAK_DURATION_SECONDS = 30  # Duration for ad placement in stream settings

# Stream statistics configuration
STATS_UPDATE_INTERVAL_SECONDS = 30  # Update stats every 30 seconds
FEATURE_STATS_ACTIVE = True  # Enable/disable stats fetching functionality

# Stream statistics configuration
COMMENT_LOGIN_PHRASE = "Путин Хуйло"
AUTHORIZED_USERS_FILE = "authorized_users.txt"
CHAT_LOG_FILE = "chat_messages.log"

# Variable to store IDs of already processed messages to avoid re-checking them
processed_message_ids = set()
last_poll_time = None
authorized_users = set()

## COMMENT LOGIN FEATURE ########################################################


def load_authorized_users():
    """Load authorized users from file."""
    global authorized_users
    if os.path.exists(AUTHORIZED_USERS_FILE):
        with open(AUTHORIZED_USERS_FILE, "r", encoding="utf-8") as f:
            for line in f:
                user = line.strip()
                if user:
                    authorized_users.add(user)
        print(authorized_users)
        print(f"✅ Loaded {len(authorized_users)} authorized users.")
    else:
        print("ℹ️ No authorization file found. Starting empty.")


load_authorized_users()


def save_authorized_user(user_id):
    """Add user to authorized list and persist to file."""
    global authorized_users
    authorized_users.add(user_id)
    with open(AUTHORIZED_USERS_FILE, "a", encoding="utf-8") as f:
        f.write(user_id + "\n")
    print(f"✅ Added '{user_id}' to authorized users and saved.")


def moderate_message_with_login(user_id, msg, item):
    if item["authorDetails"].get("isChatOwner") or item["authorDetails"].get(
        "isChatModerator"
    ):
        print("Admin")
        return

    print(user_id, COMMENT_LOGIN_PHRASE.lower(), "|||", msg.lower(), authorized_users)

    if user_id not in authorized_users:
        print("1")
        if COMMENT_LOGIN_PHRASE.lower() in msg.lower():
            print("2")
            save_authorized_user(user_id)
            print(authorized_users)
            return ""
        else:
            print("DELETE")
            return "DELETE"
    else:
        return ""


## MAIN LOGIC ###################################################################


def log_chat_message(user_id, user_name, message_text, is_removed):
    """Append chat message moderation result to log file."""
    try:
        with open(CHAT_LOG_FILE, "a", encoding="utf-8", newline="") as log_file:
            writer = csv.writer(log_file)
            writer.writerow([user_id, user_name, message_text, bool(is_removed)])
    except Exception as e:
        print(f"⚠️ Failed to log chat message: {e}")


def authenticate_youtube():
    """Authenticate via OAuth 2.0 and get the YouTube API service."""
    creds = None
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


def get_active_stream_ids(youtube):
    """Finds the user's active stream and returns its chat ID, broadcast ID, and video ID."""
    try:
        print("🔍 Searching for user broadcasts...")
        page_token = None
        active_broadcast = None

        while True:
            request = youtube.liveBroadcasts().list(
                part="snippet,contentDetails,status",
                mine=True,  # Request all user broadcasts
                maxResults=50,
                pageToken=page_token,
            )
            response = request.execute()

            if not response.get("items"):
                if response.get("nextPageToken"):
                    page_token = response["nextPageToken"]
                    continue
                print("😕 No user broadcasts found.")
                return None

            for broadcast_item in response.get("items", []):
                # Check broadcast status to find the active one
                # 'live' status means the broadcast is currently live
                # Can also check broadcast_item['status']['recordingStatus'] == 'recording'
                if broadcast_item.get("status", {}).get("lifeCycleStatus") == "live":
                    active_broadcast = broadcast_item
                    break  # Found an active broadcast

            if active_broadcast or not response.get("nextPageToken"):
                break

            page_token = response.get("nextPageToken")

        if not active_broadcast:
            print("😕 No active streams found among user broadcasts.")
            return None

        live_chat_id = active_broadcast["snippet"]["liveChatId"]
        broadcast_id = active_broadcast["id"]
        video_id = active_broadcast["id"]  # videoId is the same as the broadcast id
        stream_title = active_broadcast["snippet"]["title"]
        print(
            f"🟢 Active stream found: '{stream_title}' (Live Chat ID: {live_chat_id}, Broadcast ID: {broadcast_id}, Video ID: {video_id})"
        )
        return live_chat_id, broadcast_id, video_id
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
        return True
    except HttpError as e:
        print(f"YouTube API error when deleting message {message_id}: {e}")
    except Exception as e:
        print(f"Unknown error when deleting message {message_id}: {e}")
    return False


def post_message(youtube, live_chat_id, message_text=AD_MESSAGE_TEXT):
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


def trigger_ad_break(youtube, broadcast_id):
    """
    Insert an ad cuepoint into an active live broadcast.

    Args:
        youtube: an authorized youtube API client (scopes must include
                 https://www.googleapis.com/auth/youtube or youtube.force-ssl)
        broadcast_id: the liveBroadcast id currently streaming
    """
    body = {"cueType": "cueTypeAd", "durationSecs": int(AD_BREAK_DURATION_SECONDS)}

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


def enable_auto_ad_placement(youtube, broadcast_id):
    """
    Modify stream settings to automatically place ads during the broadcast.

    Args:
        youtube: an authorized youtube API client
        broadcast_id: the liveBroadcast id currently streaming
        ad_duration_secs: duration for ad placement in seconds (default 30)
    """
    try:
        # Get current broadcast details
        broadcast_request = youtube.liveBroadcasts().get(
            id=broadcast_id, part="snippet,contentDetails,status"
        )
        current_broadcast = broadcast_request.execute()

        # Prepare updated settings for automatic ad placement
        updated_settings = {
            "snippet": current_broadcast["snippet"],
            "contentDetails": current_broadcast["contentDetails"],
            "status": current_broadcast["status"],
        }

        # Enable automatic ad placement
        if "contentDetails" not in updated_settings:
            updated_settings["contentDetails"] = {}

        # Set ad placement settings
        updated_settings["contentDetails"]["enableAutoAdPlacement"] = True
        updated_settings["contentDetails"][
            "adBreakDuration"
        ] = AD_BREAK_DURATION_SECONDS

        # Update the broadcast with new settings
        update_request = youtube.liveBroadcasts().update(
            part="snippet,contentDetails,status", body=updated_settings
        )
        result = update_request.execute()

        print(
            f"📺 Stream settings updated for automatic ad placement (duration: {AD_BREAK_DURATION_SECONDS}s)"
        )
        print(
            f"🔄 Auto ad placement enabled: {result.get('contentDetails', {}).get('enableAutoAdPlacement', False)}"
        )
        return True

    except HttpError as e:
        print(f"YouTube API error when modifying stream settings: {e}")
        return False
    except Exception as e:
        print(f"Unknown error when modifying stream settings: {e}")
        return False


def get_stream_statistics(youtube, video_id):
    """
    Get live stream statistics including concurrent viewers and total views using YouTube Data API v3.
    This provides real concurrent viewer counts from YouTube's live streaming data.

    Args:
        youtube: an authorized youtube API client
        video_id: the YouTube video ID of the live stream

    Returns:
        dict: Dictionary containing online_viewers and total_views
    """
    try:
        # Request video details with live streaming info and statistics
        request = youtube.videos().list(
            part="liveStreamingDetails,statistics,snippet", id=video_id
        )
        response = request.execute()

        if not response["items"]:
            print(f"❌ No video found with ID: {video_id}")
            return None

        video = response["items"][0]

        # Check if it's a live stream
        if "liveStreamingDetails" not in video:
            print("⚠️ This video is not a live stream")
            return None

        live_details = video["liveStreamingDetails"]
        statistics = video["statistics"]
        snippet = video["snippet"]

        # Extract concurrent viewers from live streaming details
        concurrent_viewers = live_details.get("concurrentViewers")
        if concurrent_viewers is not None:
            concurrent_viewers = int(concurrent_viewers)
        else:
            print("⚠️ No concurrent viewers data available (stream may not be live)")
            concurrent_viewers = 0

        stats = {
            "video_id": video_id,
            "title": snippet.get("title", "N/A"),
            "channel_title": snippet.get("channelTitle", "N/A"),
            "concurrent_viewers": live_details.get("concurrentViewers"),
            "actual_start_time": live_details.get("actualStartTime"),
            "scheduled_start_time": live_details.get("scheduledStartTime"),
            "is_live": "actualEndTime" not in live_details,
            "total_views": statistics.get("viewCount"),
            "likes": statistics.get("likeCount"),
            "comments": statistics.get("commentCount"),
        }

        print(
            f"📊 Stream stats - Concurrent viewers: {stats['concurrent_viewers']}, Total views: {stats['total_views']}"
        )
        return stats

    except HttpError as e:
        print(f"❌ YouTube API error when getting stream statistics: {e}")
        return None
    except Exception as e:
        print(f"❌ Unknown error when getting stream statistics: {e}")
        return None


def update_stats_via_api(stats):
    """
    Update stats via the animation server API.

    Args:
        stats: Dictionary containing the statistics to save
    """
    try:
        # Convert the detailed stats to the format expected by the API
        api_stats = {
            "online_viewers": (
                int(stats.get("concurrent_viewers", 0))
                if stats.get("concurrent_viewers")
                else 0
            ),
            "total_views": (
                int(stats.get("total_views", 0)) if stats.get("total_views") else 0
            ),
            "last_updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            # Additional fields for the server
            "video_id": stats.get("video_id", ""),
            "title": stats.get("title", "N/A"),
            "channel_title": stats.get("channel_title", "N/A"),
            "actual_start_time": stats.get("actual_start_time", ""),
            "scheduled_start_time": stats.get("scheduled_start_time", ""),
            "is_live": stats.get("is_live", False),
            "likes": int(stats.get("likes", 0)) if stats.get("likes") else 0,
            "comments": int(stats.get("comments", 0)) if stats.get("comments") else 0,
        }

        # Make API call to update stats
        response = requests.post(
            "http://localhost:5555/api/update-stats", json=api_stats, timeout=5
        )

        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                print(
                    f"📝 Updated stats via API - Concurrent viewers: {api_stats['online_viewers']}, Total views: {api_stats['total_views']}"
                )
                return True
            else:
                print(f"❌ API returned error: {data.get('error')}")
                return False
        else:
            print(f"❌ API request failed with status: {response.status_code}")
            return False

    except requests.exceptions.ConnectionError:
        print("⚠️ Cannot connect to animation server. Stats not updated.")
        return False
    except Exception as e:
        print(f"❌ Error updating stats via API: {e}")
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
    video_id = None
    next_page_token = None
    last_ad_post_time = None
    last_moderation_time = None
    last_ad_break_time = None
    last_stream_ad_settings_time = None
    last_stats_update_time = None
    total_errors = 0

    try:
        while True:
            if not live_chat_id:
                result = get_active_stream_ids(youtube)
                if not result:
                    print(
                        f"No active streams found. Retrying in {POLL_INTERVAL_SECONDS * 5} seconds..."
                    )
                    time.sleep(POLL_INTERVAL_SECONDS * 5)
                    continue
                else:
                    live_chat_id, broadcast_id, video_id = result
                    # Reset processed messages and page token for a new stream/chat
                    processed_message_ids = set()
                    next_page_token = None
                    last_moderation_time = time.time()
                    last_ad_post_time = time.time()  # start interval for promo posting
                    last_ad_break_time = 0  # start interval for ad breaks
                    last_stream_ad_settings_time = 0
                    last_stats_update_time = 0  # start interval for stats updates
                    total_errors = 0
                    enable_auto_ad_placement(youtube, broadcast_id)
                    post_message(youtube, live_chat_id)

            now = time.time()

            # enable_auto_ad_placement(youtube, broadcast_id)

            if FEATURE_AD_ACTIVE:
                if (
                    live_chat_id
                    and last_ad_post_time is not None
                    and (now - last_ad_post_time) >= AD_MESSAGE_INTERVAL_SECONDS
                ):
                    result = post_message(youtube, live_chat_id)
                    if result:
                        print("AD POSTED")
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

            if FEATURE_STATS_ACTIVE:
                if (
                    video_id
                    and last_stats_update_time is not None
                    and (now - last_stats_update_time) >= STATS_UPDATE_INTERVAL_SECONDS
                ):
                    stats = get_stream_statistics(youtube, video_id)
                    if stats:
                        if update_stats_via_api(stats):
                            last_stats_update_time = now
                        else:
                            print("🚨 Failed to update stats via API.")
                    else:
                        total_errors += 1
                        print("🚨 Failed to get stream statistics.")

            if FEATURE_MODERATOR_ACTIVE != "":
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
                                author_channel_id = item["authorDetails"]["channelId"]
                                message_text = item["snippet"]["displayMessage"]
                            except:
                                print("Error getting message: ", item)
                                continue
                            print(
                                f"\n💬 New message from {author_name}: {message_text}"
                            )

                            if FEATURE_MODERATOR_ACTIVE == "LLM":
                                moderation_decision = moderate_message_with_llm(
                                    message_text
                                )
                            elif FEATURE_MODERATOR_ACTIVE == "LOGIN":
                                print("Login")
                                moderation_decision = moderate_message_with_login(
                                    author_channel_id, message_text, item
                                )

                            is_removed = False
                            if moderation_decision == "DELETE":
                                print(f"🚫 Inappropriate message detected. Deleting...")
                                is_removed = delete_chat_message(youtube, message_id)
                            else:
                                print("✅ Message is acceptable.")
                                is_removed = False

                            log_chat_message(
                                author_channel_id, author_name, message_text, is_removed
                            )

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
                video_id = None
                next_page_token = None
                processed_message_ids = set()
                last_ad_post_time = None
                last_moderation_time = None
                last_ad_break_time = None
                last_stats_update_time = None
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
