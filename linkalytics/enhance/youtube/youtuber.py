from apiclient.discovery import build

import re
import logging

from ... environment import cfg
from ... utils import sanitize

logging.basicConfig()
log = logging.getLogger("linkalytics.youtube")

YOUTUBE_DEVELOPER_KEY = cfg['youtube']['developer_key']
YOUTUBE_API_SERVICE_NAME = "youtube"
YOUTUBE_API_VERSION = "v3"

youtube_regex = re.compile('youtube\.com\/embed\/([^\s]*)|youtu\.be\/([^\s]*)|youtube\.com\/watch\?[^\s]*v=([^\s]*)',re.IGNORECASE)
youtube = build(YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION, developerKey=YOUTUBE_DEVELOPER_KEY)

def get_username_from_video(identity):
    vid_search = youtube.search().list(
        q=identity,
        part="id,snippet",
        maxResults=1
        ).execute()

    user = vid_search.get("items", [])[0]["snippet"]["channelTitle"]
    return user

def run(node):
    results = []
    text = sanitize(node['text'])
    for identity in re.finditer(youtube_regex, text):
        video_id = next(filter(None,identity.groups()))    # this filters out any empty matches
        results.append({
            'video_id': video_id,
            'username': get_username_from_video(video_id)
        })
    return {'youtube': results}
