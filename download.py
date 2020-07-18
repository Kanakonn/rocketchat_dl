import json
import os
import sys
from pprint import pprint

import requests
from requests import sessions
from rocketchat_API.rocketchat import RocketChat

CONFIG = {}
HISTORY = {}
ROCKET = None
CHANNELS = []

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

    while len(messages) > 0:
        for msg in messages:
            yield msg
        # Retrieve next batch of messages
        offset += count
        if history_timestamp:
            messages = ROCKET.channels_history(channel_id, count=count, offset=offset, oldest=history_timestamp).json()['messages']
        else:
            messages = ROCKET.channels_history(channel_id, count=count, offset=offset).json()['messages']


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

    if not all(x in CONFIG.keys() for x in ["user_id", "auth_token", "server", "channels"]):
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

    with sessions.Session() as session:
        ROCKET = RocketChat(user_id=CONFIG['user_id'], auth_token=CONFIG['auth_token'], server_url=CONFIG['server'], session=session)
        CHANNELS = ROCKET.channels_list().json()['channels']

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

                        _, extension = os.path.splitext(url)
                        if needs_offset:
                            filename = "{}-{}{}".format(message['_id'], offset, extension)
                        else:
                            filename = "{}{}".format(message['_id'], extension)
                        print("- Saving {} as {}...".format(url, filename))
                        attachment_data = requests.get("{}{}".format(CONFIG['server'], url)).content
                        with open(os.path.join(channel['directory'], filename), 'wb') as f:
                            f.write(attachment_data)
                        offset += 1
                        # print(attachment)

            # Write history file
            if newest_message_timestamp is not None:
                HISTORY[channel_id] = newest_message_timestamp
            with open('history.json', 'w') as f:
                f.write(json.dumps(HISTORY))
            print("Done with channel {}".format(channel['name']))

    print("Done!")
