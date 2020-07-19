import json
import mimetypes
import os
import sys
import time
from pprint import pprint

import requests
from requests import sessions
from rocketchat_API.rocketchat import RocketChat

CONFIG = {}
HISTORY = {}
ROCKET = None
CHANNELS = []
RATE_LIMIT = 0
HEADERS = {}

def get_channel_id(channel_name):
    for channel in CHANNELS:
        if channel['name'] == channel_name:
            return channel['_id']
    return None


def get_channel_history(channel_id):
    count = 100
    offset = 0
    history_timestamp = HISTORY[channel_id] if channel_id in HISTORY else None
    if history_timestamp is not None:
        messages = ROCKET.channels_history(channel_id, count=count, oldest=history_timestamp).json()['messages']
    else:
        messages = ROCKET.channels_history(channel_id, count=count).json()['messages']
    time.sleep(RATE_LIMIT)

    while len(messages) > 0:
        for msg in messages:
            yield msg
        # Retrieve next batch of messages
        offset += count
        if history_timestamp:
            messages = ROCKET.channels_history(channel_id, count=count, offset=offset, oldest=history_timestamp).json()['messages']
        else:
            messages = ROCKET.channels_history(channel_id, count=count, offset=offset).json()['messages']
        time.sleep(RATE_LIMIT)


if __name__ == "__main__":
    try:
        with open("config.json", 'r') as f:
            CONFIG = json.loads("".join(f.readlines()))
    except FileNotFoundError as e:
        print("Config file config.json not found, copy config.json.default and modify!")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print("Invalid configuration file, check config.json")
        sys.exit(2)

    if not all(x in CONFIG.keys() for x in ["user_id", "auth_token", "server", "rate_limit_ms", "channels"]):
        print("Missing one or more required config keys!")
        sys.exit(3)

    # Load history
    try:
        with open("history.json", 'r') as f:
            data = "".join(f.readlines())
            if data:
                HISTORY = json.loads(data)
    except FileNotFoundError as e:
        pass
    except json.JSONDecodeError as e:
        print("History file is corrupted! Please remove it or fix it.")
        sys.exit(4)

    RATE_LIMIT = CONFIG['rate_limit_ms'] / 1000
    HEADERS['X-Auth-Token'] = CONFIG['auth_token']
    HEADERS['X-User-Id'] = CONFIG['user_id']

    with sessions.Session() as session:
        print("Connecting to rocket.chat instance...")
        print("Rate limiter is set to {} seconds".format(RATE_LIMIT))
        ROCKET = RocketChat(user_id=CONFIG['user_id'], auth_token=CONFIG['auth_token'], server_url=CONFIG['server'], session=session)
        CHANNELS = ROCKET.channels_list().json()['channels']
        time.sleep(RATE_LIMIT)

        for channel in CONFIG['channels']:
            print("Dumping channel {}...".format(channel['name']))
            channel_id = get_channel_id(channel['name'])
            if channel_id is None:
                print("Channel {} not found!".format(channel['name']))
                continue

            if not os.path.exists(channel['directory']):
                os.makedirs(channel['directory'])

            if not os.path.isdir(channel['directory']):
                print("Directory specified for channel {} ({}) is not a directory!".format(channel['name'], channel['directory']))

            newest_message_timestamp = None
            for message in get_channel_history(channel_id):
                if newest_message_timestamp is None:
                    newest_message_timestamp = message['ts']
                if 'attachments' in message:
                    offset = 0
                    needs_offset = len(message['attachments']) > 1
                    for attachment in message['attachments']:
                        if "image_url" in attachment:
                            url = attachment['image_url']
                        if "audio_url" in attachment:
                            url = attachment['audio_url']
                        if "video_url" in attachment:
                            url = attachment['video_url']

                        extension = None
                        if "image_type" in attachment:
                            extension = mimetypes.guess_extension(attachment['image_type'])
                        if extension is None:
                            _, extension = os.path.splitext(url)

                        if needs_offset:
                            filename = "{}-{}{}".format(message['_id'], offset, extension)
                        else:
                            filename = "{}{}".format(message['_id'], extension)
                        print("- Saving {} as {}...".format(url, filename))
                        if url[0] == "/" and CONFIG['server'][-1] == "/":
                            server_url = CONFIG['server'][:-1]
                        else:
                            server_url = CONFIG['server']
                        attachment_data = session.get("{}{}".format(server_url, url), headers=HEADERS)
                        time.sleep(RATE_LIMIT)
                        if attachment_data.status_code != 200:
                            retries = 0
                            success = False
                            print("Could not save {}".format(url))
                            print("Error code {}".format(attachment_data.status_code))
                            while retries < 3 and not success:
                                print("Sleeping {}s and retrying ({}/3)".format(RATE_LIMIT * (retries + 2), retries+1))
                                time.sleep(RATE_LIMIT * (retries + 2))
                                attachment_data = session.get("{}{}".format(server_url, url), headers=HEADERS)
                                if attachment_data.status_code != 200:
                                    print("Could not save {} (try {}/3)".format(url, retries+1))
                                    print("Error code {}".format(attachment_data.status_code))
                                    retries += 1
                                else:
                                    success = True
                        with open(os.path.join(channel['directory'], filename), 'wb') as f:
                            f.write(attachment_data.content)
                        offset += 1

            # Write history file
            if newest_message_timestamp is not None:
                HISTORY[channel_id] = newest_message_timestamp
            with open('history.json', 'w') as f:
                f.write(json.dumps(HISTORY))
            print("Done with channel {}".format(channel['name']))

    print("Done!")
