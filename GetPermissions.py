from __future__ import print_function
import os, time, httplib2

from apiclient import discovery, errors
from oauth2client import client
from oauth2client import tools
from oauth2client.file import Storage

import pandas as pd

try:
    import argparse
    flags = argparse.ArgumentParser(parents=[tools.argparser]).parse_args()
except ImportError:
    flags = None

# If modifying these scopes, delete your previously saved credentials
# at ~/.credentials/drive-file-permissions.json
SCOPES = 'https://www.googleapis.com/auth/drive.metadata.readonly'
CLIENT_SECRET_FILE = 'client_secret.json'
APPLICATION_NAME = 'FilePermissions'
debug_mode = True

def print_with_prefix(prefix, out):
    print(prefix + out)
    return

def print_debug(out):
    if debug_mode:
        print_with_prefix("\t[DEBUG] : ", out)
    return

def get_credentials():
    """Gets valid user credentials from storage.

    If nothing has been stored, or if the stored credentials are invalid,
    the OAuth2 flow is completed to obtain the new credentials.

    Returns:
        Credentials, the obtained credential.
    """
    home_dir = os.path.expanduser('~')
    credential_dir = os.path.join(home_dir, '.credentials')
    if not os.path.exists(credential_dir):
        os.makedirs(credential_dir)
    credential_path = os.path.join(credential_dir, 'drive-file-permissions.json')

    store = Storage(credential_path)
    credentials = store.get()
    if not credentials or credentials.invalid:
        flow = client.flow_from_clientsecrets(CLIENT_SECRET_FILE, SCOPES)
        flow.user_agent = APPLICATION_NAME
        if flags:
            credentials = tools.run_flow(flow, store, flags)
        else: # Needed only for compatibility with Python 2.6
            credentials = tools.run(flow, store)
        print('Storing credentials to ' + credential_path)
    return credentials

def appendUser(permission, role):
    """
    Returns permission and permissions level.
    """
    user = (permission + ' Link (' + role + "),")
    if role == 'reader':
        user = (permission + ' Link (Read),')
    elif role == 'commenter':
        user = (permission + ' Link (Comment),')
    elif role == 'writer':
        user = (permission + ' Link (Write),')

    return user

def retrieve_all_files(service):
    """Retrieve a list of File resources.

    Args:
    service: Drive API service instance.
    Returns:
    List of File resources.
    """
    page_token = None
    result = []
    while True:
        param = {}
        if page_token:
            param['pageToken'] = page_token
        response = service.files().list(pageSize = 1000,**param).execute()
        result.extend(response.get('files', []))
        page_token = response.get('nextPageToken', None)
        if page_token is None:
            break
        else:
            print_debug("Page Token: " + page_token)

    return result

def main():
    """Shows shared files using the Google Drive API.

    Creates a Google Drive API service object and outputs the names and permissions
    for all files.
    """

    # Set up credentials and services
    credentials = get_credentials()
    http = credentials.authorize(httplib2.Http())
    service = discovery.build('drive', 'v3', http=http)
    file_service = service.files()

    # Get the current users email address so we don't list their information in permissions
    currentUserEmail = service.about().get(fields="user").execute()['user']['emailAddress']

    # Get all the users files and loop through them
    files = retrieve_all_files(service)
    # files = file_service.list(pageSize = 1000).execute().get('files', [])

    pd.DataFrame(files).to_csv('AllFiles.csv', index=False, encoding='utf-8')
    print('All File CSV Created')
    output = []
    for f in files:
        # Get each file
        file_shared = (file_service.get(fileId=f['id'], fields="name, shared, permissions, mimeType").execute())

        # If the file is shared then set its type and users
        #if file_shared['shared']:
        item_type = 'File'
        users = ''
        if '.folder' in file_shared['mimeType']:
            item_type = 'Folder'
        if file_shared.get('permissions'):
            for u in file_shared.get('permissions'):
                if u['type'] == 'user':
                    if u['emailAddress'] != currentUserEmail:
                        users += u['displayName'] + " (" + u['emailAddress'] + "),"
                elif u['type'] == 'anyone':
                    if u['id'] == 'anyoneWithLink':
                        users += appendUser('Shareable', u['role'])
                    elif u['id'] == 'anyone':
                        users += appendUser('Public', u['role'])

            # Add the items to the output array
        output.append({'FileType': item_type, 'FileName': file_shared['name'], 'SharedUsers': users.rstrip(',')})

        # Throtle to protect API limits
        time.sleep(.100)

    # Save output to CSV file
    pd.DataFrame(output).to_csv('FilePermissions.csv', index=False, encoding='utf-8')

if __name__ == '__main__':
    main()
