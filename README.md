Rocketchat Media Downloader
===

Small script to download images, audio and video from a rocket.chat server.

Usage
---
First copy and modify the default config. Use a user ID and auth token from the Personal Access Tokens page in your account.
Setup the channels that need to be downloaded and which directory they should be downloaded to.
```bash
cp config.json.default config.json
```
Then run the script.
```bash
python download.py
```
The script will only download messages that are new since the last time that the script ran. To download all messages again, you can modify or remove the `history.json` file.
