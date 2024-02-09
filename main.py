import os
import io
import json
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from pathlib import Path

# The SCOPES defines the level of access you are requesting from Google Drive.
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']


def main():
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

    service = build('drive', 'v3', credentials=creds)

    print("Listing files and folders:")
    initial_local_path = "./clone"  # Or any path you prefer
    # Make this directory
    os.makedirs(initial_local_path, exist_ok=True)
    list_all_files(service, 'root', '', initial_local_path)


def write_failed_folder(folder_id: str, folder_name: str, error: str):
    """
    Append a line to ./failed_folders.txt with the folder_id and error
    """
    with open('./failed_folders.txt', 'a') as f:
        f.write(f"{folder_id},{folder_name},{error}\n")


def list_all_files(service, folder_id, indent, local_path):
    page_token = None
    while True:
        # Fetch files and folders within the current folderID, accounting for pagination
        results = service.files().list(
            q=f"'{folder_id}' in parents and trashed = false",
            spaces='drive',
            fields="nextPageToken, files(id, name, mimeType)",
            pageToken=page_token,
            pageSize=100  # Explicitly specify pageSize for debugging
        ).execute()

        items = results.get('files', [])
        page_token = results.get('nextPageToken', None)

        if not items:
            print(f'{indent}No files found in folder {folder_id}.')
        else:
            for item in items:
                if item['mimeType'] == 'application/vnd.google-apps.folder':
                    # Create local directory
                    new_local_path = os.path.join(local_path, item['name'])
                    os.makedirs(new_local_path, exist_ok=True)

                    print(f"{indent}[Folder] {item['name']}")
                    try:
                        list_all_files(service, item['id'], indent + "  ", new_local_path)
                    except Exception as e:
                        print(f"{indent}Failed to list folder {item['name']} with error: {e}")
                        write_failed_folder(item['id'], local_path, str(e))
                else:
                    # Download the file
                    file_path = os.path.join(local_path, item['name'] + '.pdf' if item['mimeType'].startswith('application/vnd.google-apps.') else item['name'])
                    print(f"{indent}[Downloading file] {item['name']}")
                    download_file(service, item['id'], file_path, item['mimeType'])

        if page_token is None:
            print(f"{indent}Completed folder {folder_id}.")
            break
        else:
            print(f"{indent}Fetching next page for folder {folder_id} with token {page_token}.")


def sanitize_path(path: str) -> Path:
    """
    Trim the stem to make it less than 255 chars
    """
    stem = Path(path).stem
    if len(stem) > 250:
        stem = stem[:245]  # This is the limit because we add .temp
    return Path(path).with_stem(stem)


def download_file(service, file_id, file_path, mime_type):
    sanitized_path = sanitize_path(file_path)
    temp_path = Path(str(sanitized_path) + ".temp")

    # Check if file already exists
    if os.path.exists(sanitized_path):
        print(f"File {sanitized_path} already exists. Skipping download.")
        return

    # Determine the appropriate method to download the file based on its MIME type
    if mime_type.startswith('application/vnd.google-apps.'):
        # It's a Google Workspace document, so we'll export it as a PDF.
        request = service.files().export_media(fileId=file_id,
                                               mimeType='application/pdf')
        sanitized_path = sanitized_path.with_suffix('.pdf')  # Ensure the file has a .pdf extension
    else:
        # It's a different kind of file, download without conversion.
        request = service.files().get_media(fileId=file_id)

    fh = io.FileIO(temp_path, 'wb')
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        status, done = downloader.next_chunk()
        print(f"Download {int(status.progress() * 100)}%.")

    # Rename the temp file to the final file name
    os.rename(temp_path, sanitized_path)
    print(f"Downloaded '{sanitized_path}' successfully.")


if __name__ == '__main__':
    main()
