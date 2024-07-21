from __future__ import print_function

from enum import Enum
import os.path
import re
from typing import List

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build, Resource
from googleapiclient.errors import HttpError

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


class GoogleSheet:

    class TabStatus(Enum):
        FINISHED = "finished"
        IN_PROGRESS = "in-progress"
        GAME_CREATION = "game creation"
        NOT_STARTED = "not started"

        @staticmethod
        def from_string(s: str):
            match s:
                case "finished":
                    return GoogleSheet.TabStatus.FINISHED
                case "in-progress":
                    return GoogleSheet.TabStatus.IN_PROGRESS
                case "game creation":
                    return GoogleSheet.TabStatus.GAME_CREATION
                case _:
                    return GoogleSheet.TabStatus.NOT_STARTED

    def __init__(self, config):
        self.dryrun = "dryrun" in config and config["dryrun"]
        creds = None
        # The file token.json stores the user's access and refresh tokens, and is
        # created automatically when the authorization flow completes for the first
        # time.
        if os.path.exists("token.json"):
            creds = Credentials.from_service_account_file("token.json", scopes=SCOPES)

        try:
            service: Resource = build("sheets", "v4", credentials=creds)

            # Call the Sheets API
            self.sheet: Resource = service.spreadsheets() # type: ignore
            self.spreadsheet_id = config["spreadsheet_id"]
            # result = self.sheet.values().get(spreadsheetId=config["spreadsheet_id"],
            #                         range="Summary!A1:O128").execute()
            # values = result.get('values', [])
            # print(values)
        except HttpError as err:
            print(err)

    def get_rows(self, range) -> List[List[str]]:
        try:
            return (
                self.sheet.values() # type: ignore
                .get(spreadsheetId=self.spreadsheet_id, range=range)
                .execute()["values"]
            )
        except:
            return []

    def get_rows_formulas(self, range) -> List[List[str]]:
        try:
            return (
                self.sheet.values() # type: ignore
                .get(
                    spreadsheetId=self.spreadsheet_id,
                    range=range,
                    valueRenderOption="FORMULA",
                )
                .execute()["values"]
            )
        except:
            return []

    def update_rows_raw(self, range, data):
        if self.dryrun:
            print("Running dryun on update_rows_raw and not updating sheet")
        else:
            return (
                self.sheet.values() # type: ignore
                .update(
                    spreadsheetId=self.spreadsheet_id,
                    range=range,
                    valueInputOption="USER_ENTERED",
                    body={"values": data},
                )
                .execute()
            )

    def get_sheet_tabs_data(self):
        return self.sheet.get(spreadsheetId=self.spreadsheet_id).execute().get("sheets") # type: ignore

    def get_game_tabs(self) -> List[str]:
        """
        Returns a list of the google sheets tabs containing games.
        """
        game_tabs = []
        sheets = self.get_sheet_tabs_data()
        for tab in sheets:
            # Get the tabs that we should parse
            # Should be any tab that starts with "_"
            if re.search("^_", tab["properties"]["title"]):
                game_tabs.append(tab["properties"]["title"])
        return game_tabs

    def get_tab_status(self, tab: str) -> TabStatus:
        tab_status = self.get_rows(f"{tab}!A1")

        try:
            return GoogleSheet.TabStatus.from_string(tab_status[0][0])
        except IndexError:
            return GoogleSheet.TabStatus.NOT_STARTED

    def get_tabs_by_status(self, status: "GoogleSheet.TabStatus") -> List[str]:
        tabs = self.get_game_tabs()
        return [tab for tab in tabs if self.get_tab_status(tab) == status]
