

import json
import re
from typing import List
from api import API
from sheet import GoogleSheet


class GetFunStats:

    def __init__(self, config):
        self.config = config
        self.sheet = GoogleSheet(config)
        self.api = API(config)

    def get_game_tabs(self) -> List[str]:
        """
        Returns a list of the google sheets tabs containing games.
        """
        game_tabs = []
        sheets = self.sheet.get_sheet_tabs_data()
        for tab in sheets:
            # Get the tabs that we should parse
            # Should be either `R# Games` or `R# Games 2v2`
            if re.search("^R\d Games", tab["properties"]["title"]):
                game_tabs.append(tab["properties"]["title"])
        return game_tabs

    def convert_wz_game_link_to_id(self, game_link: str):
        return game_link[43:]

    def run(self):
        games_with_chat = {}
        for tab in self.get_game_tabs():
            print(f"checking the following tab: {tab}")
            is_2v2 = "2v2" in tab
            tab_rows = self.sheet.get_rows(f"{tab}!A1:{'J' if is_2v2 else'F'}300")
            games_with_chat[tab] = []
            for row in tab_rows:
                if row and self.api.check_game(self.convert_wz_game_link_to_id(row[0])):
                    games_with_chat[tab].append(row)
            print(f"found {len(games_with_chat[tab])} games in {tab}\n")
        with open("data/games_with_chat.json", "w", encoding="utf-8") as output_file:
            json.dump(games_with_chat, output_file)
            
            
