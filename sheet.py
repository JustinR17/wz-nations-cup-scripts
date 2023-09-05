from __future__ import print_function

import os.path
from typing import List

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build, Resource
from googleapiclient.errors import HttpError

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

class GoogleSheet:

    def __init__(self, config):
        self.dryrun = "dryrun" in config and config["dryrun"]
        creds = None
        # The file token.json stores the user's access and refresh tokens, and is
        # created automatically when the authorization flow completes for the first
        # time.
        if os.path.exists('token.json'):
            creds = Credentials.from_service_account_file('token.json', scopes=SCOPES)

        try:
            service: Resource = build('sheets', 'v4', credentials=creds)

            # Call the Sheets API
            self.sheet: Resource = service.spreadsheets()
            self.spreadsheet_id = config["spreadsheet_id"]
            # result = self.sheet.values().get(spreadsheetId=config["spreadsheet_id"],
            #                         range="Summary!A1:O128").execute()
            # values = result.get('values', [])
            # print(values)
        except HttpError as err:
            print(err)
    
    def get_rows(self, range) -> List[List[str]]:
        try:
            return self.sheet.values().get(spreadsheetId=self.spreadsheet_id, range=range).execute()["values"]
        except:
            return []

    def update_rows_raw(self, range, data):
        if self.dryrun:
            print("Running dryun on update_rows_raw and not updating sheet")
        else:
            return self.sheet.values().update(spreadsheetId=self.spreadsheet_id, range=range, valueInputOption="USER_ENTERED", body={"values": data}).execute()
    
    def get_sheet_tabs_data(self):
        return self.sheet.get(spreadsheetId=self.spreadsheet_id).execute().get("sheets")
