#!/usr/bin/env python3

import os
import sys
import base64
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import glob

SCOPES = ['https://mail.google.com/']

def authenticate_gmail():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    else:
        flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
        creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    return build('gmail', 'v1', credentials=creds)

def clear_gmail_mailbox(service):
    try:
        for label in ['INBOX', 'SENT']:
            results = service.users().messages().list(userId='me', labelIds=[label]).execute()
            messages = results.get('messages', [])
            
            if not messages:
                print(f"{label} is already empty.")
                continue
            
            print(f"Found {len(messages)} messages in {label}. Deleting...")
            message_ids = [msg['id'] for msg in messages]
            batch_delete_request = {'ids': message_ids}
            
            service.users().messages().batchDelete(userId='me', body=batch_delete_request).execute()
            print(f"Successfully deleted {len(message_ids)} messages from {label}.")
    
    except HttpError as error:
        print(f'Error clearing mailbox: {error}')
    except Exception as e:
        print(f'Unexpected error while clearing mailbox: {e}')


def upload_eml_file(service, eml_path):
    try:
        with open(eml_path, 'rb') as f:
            raw_message = base64.urlsafe_b64encode(f.read()).decode()

        message = {'raw': raw_message, 'labelIds': ['INBOX']}
        uploaded_msg = service.users().messages().insert(userId='me', body=message).execute()
        print(f"Successfully uploaded: {os.path.basename(eml_path)} (ID: {uploaded_msg['id']})")
        return True
    except HttpError as error:
        print(f'Error uploading {os.path.basename(eml_path)}: {error}')
        return False
    except Exception as e:
        print(f'Unexpected error with {os.path.basename(eml_path)}: {e}')
        return False

def upload_all_eml_files(directory):
    service = authenticate_gmail()
    
    print("Clearing Gmail inbox and sent mail before upload...")
    clear_gmail_mailbox(service)
    print()
    
    eml_files = glob.glob(os.path.join(directory, '*.eml'))
    
    if not eml_files:
        print(f"No .eml files found in {directory}")
        return
    
    print(f"Found {len(eml_files)} .eml files to upload")
    successful = 0
    failed = 0
    
    for eml_file in eml_files:
        if upload_eml_file(service, eml_file):
            successful += 1
        else:
            failed += 1
    
    print(f"\nUpload complete:")
    print(f"Successfully uploaded: {successful}")
    print(f"Failed to upload: {failed}")

def main():
    if len(sys.argv) != 2:
        print("Usage: python add_fake_mail.py <item_id>")
        sys.exit(1)
    
    try:
        item_id = int(sys.argv[1])
    except ValueError:
        print("Error: Item ID must be an integer")
        sys.exit(1)
    
    directory = f'data/converted/item{item_id}'
    
    print(f"Processing item {item_id}")
    print(f"Directory: {directory}")
    
    if not os.path.exists(directory):
        print(f"Error: Directory {directory} does not exist")
        sys.exit(1)
    
    upload_all_eml_files(directory)

if __name__ == '__main__':
    main()