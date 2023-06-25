

import json
from typing import List
from NCTypes import Game, Matchup, Player, Team
from api import API
from sheet import GoogleSheet


class CreateGames:

    def __init__(self, config):
        self.config = config
        self.sheet = GoogleSheet(config)
        self.api = API(config)
    
    def run(self, sheet_name: str, round: str, template: str):
        """
        Reads the sheet_name matchups and creates games. The sheet will be updated with the game links
        """
        matchups = self.parse_sheet_matchups(self, round)
        matchups = self.create_games(matchups, template)
        self.write_games(sheet_name, matchups, round)

    def parse_sheet_matchups(self, round):
        with open(f"data/matchups_output_r{round}.json", "r", encoding="utf-8") as json_file:
            json_data = json.load(json_file)

            # Need to recreate matchup/game structure from dictionaries & lists
            matchups: List[Matchup] = []
            for matchup in json_data:
                teams = [
                    Team(matchup["teams"][0]["name"]),
                    Team(matchup["teams"][1]["name"])
                ]

                teams[0] = List(map(lambda e: Player(e["name"], e["id"], teams[0]), matchup["teams"][0]["players"]))
                teams[1] = List(map(lambda e: Player(e["name"], e["id"], teams[1]), matchup["teams"][1]["players"]))


                matchups.append(Matchup(teams[0], teams[1]))
                for game in matchup["games"]:
                    matchups[-1].games.append(Game(
                        [],
                        Game.Outcome.UNDEFINED,
                        ""
                    ))
        
        return matchups
    
    def create_games(self, matchups: List[Matchup], template) -> List[Matchup]:
        for matchup in matchups:
            print(f"Beginning game creation for {matchup.teams[0].name} vs. {matchup.teams[1].name}")

            for game in matchup.games:

                title = f"Nations' Cup 2023 - {matchup.teams[0].name} vs. {matchup.teams[1].name}"
                description = f"""This game is a part of the Nations' Cup, run by Marcus (https://docs.google.com/spreadsheets/d/1QPKGgwToBd2prap8u3XVUx9F47SuvMH9wJruvG0t2D4). 

Match is between:
\t{game.players[0].name} in {matchup.teams[0].name}
\t{game.players[1].name} in {matchup.teams[1].name}
"""
                
                try:
                    game_link = self.api.create_game([game.players[0].id, game.players[0].id], template, title, description)

                    if game_link:
                        print(f"\tGame created between {game.players[0].name} & {game.players[1].name} - {game_link}")
                        game.link = game_link
                except API.GameCreationException as e:
                    print(f"\tUnable to create game between {game.players[0].name} & {game.players[1].name}: '{str(e)}'")
        
        return matchups

    def write_games(self, sheet_name: str, matchups: List[Matchup], round: str):
        """
        Output the matchups to a file for safety and to the google sheets
        """

        # Output to file first since this is safer
        with open(f"data/games_output_r{round}.json", "w", encoding="utf-8") as output_file:
            print("JSON version of matchups data is stored to 'matchups_output.json'")
            json.dump(matchups, output_file)

        sheet_data: List[List[str]] = []
        for matchup in matchups:
            sheet_data.append([matchup.teams[0], 0, "vs.", matchup.teams[1], 0])
            for game in matchup.games:
                sheet_data.append([game.players[0].name, game.players[0].id, "", game.players[0].name, game.players[0].id, game.link])
            sheet_data.append([]) # Empty row to divide teams
        
        # Updating the sheet involves matching the matchups object to the sheet rows
        sheet_data = self.sheet.get_rows(f"{sheet_name}!A1:F{len(sheet_data)}")
        updated_game_links = []

        current_matchup = None
        for row in sheet_data:
            if not row:
                current_matchup = None
                updated_game_links.append("")
            elif row and not current_matchup:
                # New matchup
                for matchup in matchups:
                    if row[0] == matchup.teams[0] or row[0] == matchup.teams[1]:
                        current_matchup = matchup
                updated_game_links.append("")
            elif row:
                # New game link to add
                for game in current_matchup.games:
                    if int(row[1]) == game.players[0].id and int(row[4]) == game.players[1].id or int(row[1]) == game.players[1].id and int(row[4]) == game.players[0].id:
                        updated_game_links.append(game.link)
                        break                
        self.sheet.update_rows_raw(f"{sheet_name}!F1:F{len(updated_game_links)}", updated_game_links)



