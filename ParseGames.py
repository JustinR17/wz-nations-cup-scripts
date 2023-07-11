import json
from typing import Dict, List
from NCTypes import Game, Matchup, Player, Team, WarzoneGame, WarzonePlayer
from api import API
from sheet import GoogleSheet
import re


class ParseGames:

    def __init__(self, config):
        self.config = config
        self.sheet = GoogleSheet(config)
        self.api = API(config)
    
    def run(self):
        """
        Reads the google sheets games and updates finished games. Newly finished games are stored in a buffer file for the discord bot to read
        """
        newly_finished_games = self.update_new_games()
        self.write_newly_finished_games(newly_finished_games)

    
    def update_new_games(self) -> Dict[str, List[WarzoneGame]]:
        """
        Checks all game tabs for games that have newly finished. Writes the new results in the tab.

        Returns a dictionary of lists (tab name -> List[Games])
        """
        
        newly_finished_games: Dict[str, List[WarzoneGame]] = {}
        for tab in self.get_game_tabs():
            tab_rows = self.sheet.get_rows(f"{tab}A1:F300")

            team_a, team_b = "", ""
            for row in tab_rows:
                if not row:
                    # Finished the previous matchup
                    team_a, team_b = "", ""
                else:
                    if not team_a and not team_b:
                        # New teams to add
                        team_a, team_b = row[0], row[3]
                    elif not row[2]:
                        # Game to check
                        game = self.api.check_game(self.convert_wz_game_link_to_id(row[5]))
                        if game.players[0].id != row[1]:
                            game.players.reverse()
                        
                        if game.outcome == Game.Outcome.FINISHED:
                            # TODO check these game outcomes
                            game.players[0].team, game.players[1].team = team_a,  team_b
                            newly_finished_games.setdefault(tab, []).append(game)
                            
                            if game.players[0].outcome == WarzonePlayer.Outcome.WON and game.players[0].id == row[1]:
                                # Left team wins
                                row[2] = "defeats"
                            else:
                                row[2] = "loses to"
            self.sheet.update_rows_raw(f"{tab}A1:F300", tab_rows)
        return newly_finished_games
    
    def get_game_tabs(self) -> List[str]:
        game_tabs = []
        sheets = self.sheet.get_sheet_tabs_data()
        for tab in sheets:
            # Get the tabs that we should parse
            if re.search("^R\d Games$", tab["properties"]["title"]):
                game_tabs.append(tab["properties"]["title"])
        return game_tabs

    def convert_wz_game_link_to_id(self, game_link: str):
        return game_link[45:]
    
    def write_newly_finished_games(self, newly_finished_games: Dict[str, List[WarzoneGame]]):
        """
        Combines the existing newly_finished_games that have not been posted yet with the newly finished games from this check
        """

        # Output to file first since this is safer
        with open (f"data/newly_finished_games.json", "w", encoding="utf-8") as input_file:
            buffer_newly_finished_games = json.load(input_file)
            conmbined_newly_finished = { key:buffer_newly_finished_games.get(key,[])+newly_finished_games.get(key,[]) for key in set(list(buffer_newly_finished_games.keys())+list(newly_finished_games.keys())) }
        
        with open(f"data/newly_finished_games.json", "w", encoding="utf-8") as output_file:
            print("JSON version of newly finished games saved to 'newly_finished_games.json'")
            json.dump(conmbined_newly_finished, output_file)

