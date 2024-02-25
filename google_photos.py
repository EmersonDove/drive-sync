import os

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import requests
from pathlib import Path
import uuid

# Folder to save the downloaded photos
download_folder = './photos'
duplicate_folder = './photos/duplicate'

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


def download_photos():
    creds = login()
    service = build('photoslibrary', 'v1', credentials=creds, static_discovery=False)

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
                modifier = '=d'   # Modifier for downloading the full resolution image

            file_path = os.path.join(download_folder, item['filename'])
            download_url = item['baseUrl'] + modifier
            response = requests.get(download_url)
            if response.status_code == 200:
                if not os.path.exists(file_path):  # Avoid re-downloading files
                    with open(file_path, 'wb') as f:
                        f.write(response.content)
                    print(f'Downloaded {item["filename"]}')
                else:
                    # Write the file to a /duplicate/ folder as a uuid with the same suffix
                    print(f'Duplicate file found: {item["filename"]}')
                    path_split = Path(file_path)
                    new_path = path_split.parent / 'duplicate' / f'{path_split.stem}-{uuid.uuid4()}{path_split.suffix}'
                    with open(new_path, 'wb') as f2:
                        f2.write(response.content)
            else:
                print(f'Failed to download {item["filename"]}')

        if not nextPageToken:
            break  # Exit the loop if there's no more pages to fetch
        else:
            print("Got another page!")


if __name__ == '__main__':
    if not os.path.exists(download_folder):
        os.makedirs(download_folder)

    if not os.path.exists(duplicate_folder):
        os.makedirs(duplicate_folder)

    download_photos()