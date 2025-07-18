import json
import re
from typing import List
from api import API
from sheet import GoogleSheet
from utils import log_exception, log_message


class GetFunStats:

    def __init__(self, config):
        self.config = config
        self.sheet = GoogleSheet(config)
        self.api = API(config)

    def convert_wz_game_link_to_id(self, game_link: str):
        return game_link[43:]

    def run(self):
        try:
            log_message("Running GetFunStats", "GetFunStats.run")
            tabs_to_update = self.sheet.get_tabs_by_status(
                [GoogleSheet.TabStatus.IN_PROGRESS, GoogleSheet.TabStatus.FINISHED]
            )

            games_with_chat = {}
            for tab in tabs_to_update:
                log_message(f"checking the following tab: {tab}", "GetFunStats.run")
                is_finals = "_Finals" in tab
                tab_rows = self.sheet.get_rows(
                    f"{tab}!{'L2:Q300' if is_finals else'K2:P350'}"
                )
                games_with_chat[tab] = []
                for row in tab_rows:
                    if row and len(row) == 6 and "?GameID" in row[5]:
                        chat = self.api.get_game_chat(
                            self.convert_wz_game_link_to_id(row[-1])
                        )
                        if chat:
                            games_with_chat[tab].append((row + chat))
                print(f"found {len(games_with_chat[tab])} games in {tab}\n")
            with open(
                "data/games_with_chat.json", "w", encoding="utf-8"
            ) as output_file:
                json.dump(games_with_chat, output_file)
        except Exception as e:
            log_exception(e)
