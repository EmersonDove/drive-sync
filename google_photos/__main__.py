import os

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import requests
from pathlib import Path
import uuid
from database import Asset, FailedAsset, session
import datetime
from dateutil import parser
import logging

# Folder to save the downloaded photos
download_folder = './photos'

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/photoslibrary.readonly']


def login():
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'client_secret.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    return creds


def download_photos(creds_):
    service = build('photoslibrary', 'v1', credentials=creds_, static_discovery=False)

    nextPageToken = None
    while True:
        # Adjust your API call as needed; this is a basic example
        results = service.mediaItems().list(
            pageSize=100,
            fields="nextPageToken,mediaItems(baseUrl,filename,mediaMetadata)",
            pageToken=nextPageToken).execute()
        items = results.get('mediaItems', [])
        nextPageToken = results.get('nextPageToken')

        if not items:
            print('No files found.')
            return

        for item in items:
            # Determine if the item is a video or an image
            if 'video' in item['mediaMetadata']:
                modifier = '=dv'  # Modifier for downloading the original video
            else:
                modifier = '=d'  # Modifier for downloading the full resolution image

            file_path = os.path.join(download_folder, item['filename'])
            download_url = item['baseUrl'] + modifier
            response = requests.get(download_url)
            if response.status_code == 200:
                path_split = Path(file_path)
                file_id = f'{path_split.stem}-{uuid.uuid4()}{path_split.suffix}'
                new_path = path_split.parent / file_id
                with open(new_path, 'wb') as f2:
                    f2.write(response.content)

                with session() as db:
                    db.add(Asset(
                        id=str(uuid.uuid4()),
                        creation_time=parser.parse(item['mediaMetadata']['creationTime']),
                        filename=item['filename'],
                        suffix=path_split.suffix,
                        asset_metadata=item['mediaMetadata'],
                        file_id=file_id,
                        physical_path=str(new_path),
                    ))

                logging.info(f"Downloaded {item['filename']} - shot at {item['mediaMetadata']['creationTime']}")
            else:
                # Write a failed assets object to database
                with session() as db:
                    db.add(FailedAsset(
                        id=str(uuid.uuid4()),
                        filename=item['filename'],
                        error=response.text
                    ))
                logging.error(f"Failed to download {item['filename']} - {response.status_code}")

        if not nextPageToken:
            break  # Exit the loop if there's no more pages to fetch
        else:
            print("Got another page!")


if __name__ == '__main__':
    creds = login()

    if not os.path.exists(download_folder):
        os.makedirs(download_folder)

    download_photos(creds)
