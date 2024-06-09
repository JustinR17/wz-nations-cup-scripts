

import json
from typing import List
from NCTypes import Game, Matchup
from api import API
from sheet import GoogleSheet
import jsonpickle

from utils import log_exception, log_message


PLAYER_COUNT_TO_LINK_COLUMN = {
    1: "F",
    2: "J"
}

class CreateGames:

    def __init__(self, config):
        self.config = config
        self.sheet = GoogleSheet(config)
        self.api = API(config)
    
    def run(self, sheet_name: str, round: str, template: str, players_per_team: int):
        """
        Reads the sheet_name matchups and creates games. The sheet will be updated with the game links
        """
        try:
            log_message("Running CreateGames", "CreateGames.run")
            matchups = self.parse_sheet_matchups(round)

            # Did not want to mix up the flows too much so separated 1v1s and 2v2s
            if players_per_team == 1:
                matchups = self.create_games(matchups, round, template)
                self.write_games(sheet_name, matchups, round)
            elif players_per_team == 2:
                matchups = self.create_2v2_games(matchups, round, template)
                self.write_2v2_games(sheet_name, matchups, round)
            elif players_per_team == -1:
                self.patch_broken_2v2_games(sheet_name, matchups, round, template)
            else:
                raise Exception(f"Invalid players_per_team argument provided: '{players_per_team}'")
            
            
        except Exception as e:
            log_exception(e)

    def parse_sheet_matchups(self, round):
        with open(f"data/matchups_output_r{round}.json", "r", encoding="utf-8") as json_file:
            json_data: List[Matchup] = jsonpickle.decode(json.load(json_file))
        
        return json_data
    
    def create_games(self, matchups: List[Matchup], round: int, template: str) -> List[Matchup]:
        for matchup in matchups:
            log_message(f"Beginning game creation for {matchup.teams[0].name} vs. {matchup.teams[1].name}", "create_games")

            for game in matchup.games:

                title = f"Nations' Cup 2023 R{round} {matchup.teams[0].name} vs. {matchup.teams[1].name}"
                description = f"""This game is a part of the Nations' Cup R{round}, run by Marcus. You have 3 days to join the game.
                
Match is between:
\t{game.players[0].name.encode()} in {matchup.teams[0].name}
\t{game.players[1].name.encode()} in {matchup.teams[1].name}

https://docs.google.com/spreadsheets/d/1QPKGgwToBd2prap8u3XVUx9F47SuvMH9wJruvG0t2D4
"""
                
                try:
                    game_link = self.api.create_game([(game.players[0].id,matchup.teams[0].name) , (game.players[1].id,matchup.teams[1].name)], template, title, description)

                    if game_link:
                        log_message(f"\tGame created between {game.players[0].name.encode()} & {game.players[1].name.encode()} - {game_link}", "create_games")
                        game.link = game_link
                except API.GameCreationException as e:
                    log_exception(f"\tGameCreationException: Unable to create game between {game.players[0].name.encode()} & {game.players[1].name.encode()}: '{str(e)}'")
                except Exception as e:
                    log_exception(f"\tUnknown Exception: Unable to create game between {game.players[0].name.encode()} & {game.players[1].name.encode()}: '{str(e)}'")
        
        return matchups

    def write_games(self, sheet_name: str, matchups: List[Matchup], round: str):
        """
        Output the matchups to a file for safety and to the google sheets
        """

        # Output to file first since this is safer
        with open(f"data/games_output_r{round}.json", "w", encoding="utf-8") as output_file:
            log_message("JSON version of matchups data is stored to 'matchups_output.json'", "write_games")
            json.dump(jsonpickle.encode(matchups), output_file)

        sheet_data: List[List[str]] = []
        for matchup in matchups:
            sheet_data.append([matchup.teams[0], 0, "vs.", matchup.teams[1], 0])
            for game in matchup.games:
                sheet_data.append('')
            sheet_data.append('') # Empty row to divide teams
        
        # Updating the sheet involves matching the matchups object to the sheet rows
        sheet_data = self.sheet.get_rows(f"{sheet_name}!A1:F{len(sheet_data)}")
        updated_game_links = []

        current_matchup = None
        for row in sheet_data:
            if not row:
                current_matchup = None
                updated_game_links.append([""])
            elif row and not current_matchup:
                # New matchup
                for matchup in matchups:
                    if row[0].strip() == matchup.teams[0].name or row[0].strip() == matchup.teams[1].name:
                        current_matchup = matchup
                updated_game_links.append([""])
            elif row:
                # New game link to add
                has_added_game = False
                for game in current_matchup.games:
                    if row[1].strip() == game.players[0].id and row[4].strip() == game.players[1].id or row[1].strip() == game.players[1].id and row[4].strip() == game.players[0].id:
                        updated_game_links.append([f"{API.GAME_URL}{game.link}"])
                        # Need to remove games in case there are scenarios where two players get matched up twice (ie. 3 players per team)
                        current_matchup.games.remove(game)
                        has_added_game = True
                        break
                if not has_added_game:
                    updated_game_links.append([""])
        self.sheet.update_rows_raw(f"{sheet_name}!F1:F{len(updated_game_links)}", updated_game_links)
        log_message(f"Updated the google sheet with {len(updated_game_links)} new links", "write_games")


    #############################
    ######## 2v2 VERSION ########
    #############################

    def create_2v2_games(self, matchups: List[Matchup], round: int, template: str) -> List[Matchup]:
        for matchup in matchups:
            log_message(f"Beginning game creation for {matchup.teams[0].name} vs. {matchup.teams[1].name}", "create_2v2_games")

            for game in matchup.games:

                title = f"Nations' Cup 2023 R{round} {matchup.teams[0].name} vs. {matchup.teams[1].name}"
                players_by_team = game.get_player_names_by_team()
                description = f"""This game is a part of the Nations' Cup R{round}, run by Marcus. You have 3 days to join the game.
                
Match is between:
\t{", ".join(players_by_team[matchup.teams[0].name]).encode()} in {matchup.teams[0].name}
\t{", ".join(players_by_team[matchup.teams[1].name]).encode()} in {matchup.teams[1].name}

https://docs.google.com/spreadsheets/d/1QPKGgwToBd2prap8u3XVUx9F47SuvMH9wJruvG0t2D4
"""
                
                try:
                    game_link = self.api.create_game(list(map(lambda e: (e.id, e.team.name), game.players)), template, title, description)
                    if game_link:
                        log_message(f"\tGame created between {game} - {game_link}", "create_2v2_games")
                        game.link = game_link
                except API.GameCreationException as e:
                    log_exception(f"\tGameCreationException: Unable to create game between {game.players[0].name.encode()} & {game.players[1].name.encode()}: '{str(e)}'")
                except Exception as e:
                    log_exception(f"\tUnknown Exception: Unable to create game between {game.players[0].name.encode()} & {game.players[1].name.encode()}: '{str(e)}'")
        
        return matchups

    def write_2v2_games(self, sheet_name: str, matchups: List[Matchup], round: str):
        """
        Output the matchups to a file for safety and to the google sheets
        """

        # Output to file first since this is safer
        with open(f"data/games_output_r{round}.json", "w", encoding="utf-8") as output_file:
            log_message("JSON version of matchups data is stored to 'matchups_output.json'", "write_2v2_games")
            json.dump(jsonpickle.encode(matchups), output_file)
        
        sheet_data: List[List[str]] = []
        for matchup in matchups:
            sheet_data.append([matchup.teams[0], 0, "vs.", matchup.teams[1], 0])
            for game in matchup.games:
                sheet_data.append('')
            sheet_data.append('') # Empty row to divide teams
        
        # Updating the sheet involves matching the matchups object to the sheet rows
        sheet_data = self.sheet.get_rows(f"{sheet_name}!A1:J{len(sheet_data)}")
        updated_game_links = []
        num_players = 1

        current_matchup = None
        for row in sheet_data:
            if not row:
                current_matchup = None
                updated_game_links.append([""])
            elif row and not current_matchup:
                # New matchup
                for matchup in matchups:
                    if row[0].strip() == matchup.teams[0].name or row[0].strip() == matchup.teams[1].name:
                        current_matchup = matchup
                updated_game_links.append([""])
            elif row:
                # New game link to add
                has_added_game = False
                for game in current_matchup.games:
                    num_players = len(game.players) // 2
                    sorted_players = sorted(game.players)

                    # Check if game in matchup matches the row
                    does_game_match_row = True
                    for i in range(num_players):
                        if row[2*i+1] != str(sorted_players[i].id) or row[2*num_players+2*i+2] != str(sorted_players[num_players+i].id):
                            does_game_match_row = False
                            break
                    
                    # if game does match, add the link and remove the game from the matchup
                    if does_game_match_row:
                        updated_game_links.append([f"{API.GAME_URL}{game.link}"])
                        # Need to remove games in case there are scenarios where two players get matched up twice (ie. 3 players per team)
                        current_matchup.games.remove(game)
                        has_added_game = True
                        break

                if not has_added_game:
                    updated_game_links.append([""])
        print(updated_game_links)
        # Need a map from the link column depending on the players
        self.sheet.update_rows_raw(f"{sheet_name}!{PLAYER_COUNT_TO_LINK_COLUMN[num_players]}1:{PLAYER_COUNT_TO_LINK_COLUMN[num_players]}{len(updated_game_links)}", updated_game_links)
        log_message(f"Updated the google sheet with {len(updated_game_links)} new links", "write_2v2_games")


    #############################
    ########### PATCH ###########
    #############################

    def create_individual_game(self, game: Game, matchup: Matchup, template: str, round: int):
        title = f"Nations' Cup 2023 R{round} {matchup.teams[0].name} vs. {matchup.teams[1].name}"
        players_by_team = game.get_player_names_by_team()
        description = f"""This game is a part of the Nations' Cup R{round}, run by Marcus. You have 3 days to join the game.
        
Match is between:
\t{", ".join(players_by_team[matchup.teams[0].name]).encode()} in {matchup.teams[0].name}
\t{", ".join(players_by_team[matchup.teams[1].name]).encode()} in {matchup.teams[1].name}

https://docs.google.com/spreadsheets/d/1QPKGgwToBd2prap8u3XVUx9F47SuvMH9wJruvG0t2D4
"""
        
        try:
            game_link = self.api.create_game(list(map(lambda e: (e.id, e.team.name), game.players)), template, title, description)
            if game_link:
                log_message(f"\tGame created between {game} - {game_link}", "create_2v2_games")
                game.link = game_link
        except API.GameCreationException as e:
            log_exception(f"\tGameCreationException: Unable to create game between {game.players[0].name.encode()} & {game.players[1].name.encode()}: '{str(e)}'")
        except Exception as e:
            log_exception(f"\tUnknown Exception: Unable to create game between {game.players[0].name.encode()} & {game.players[1].name.encode()}: '{str(e)}'")

    def patch_broken_2v2_games(self, sheet_name: str, matchups: List[Matchup], round: int, template: str) -> List[Matchup]:
        # Updating the sheet involves matching the matchups object to the sheet rows
        sheet_data = self.sheet.get_rows(f"{sheet_name}!A1:J{121}")
        num_players = 1

        current_matchup = None
        for row in sheet_data:
            if not row or not row[0]:
                # End of matchup
                current_matchup = None
            elif row and not current_matchup:
                # New matchup
                for matchup in matchups:
                    if row[0].strip() == matchup.teams[0].name or row[0].strip() == matchup.teams[1].name:
                        current_matchup = matchup
            elif row and (len(row) < 10 or not row[9]):
                # New game link to add
                for game in current_matchup.games:
                    num_players = len(game.players) // 2
                    sorted_players = sorted(game.players)

                    # Check if game in matchup matches the row
                    does_game_match_row = True
                    for i in range(num_players):
                        if row[2*i+1] != str(sorted_players[i].id) or row[2*num_players+2*i+2] != str(sorted_players[num_players+i].id):
                            does_game_match_row = False
                            break
                    
                    # if game does match, add the link and remove the game from the matchup
                    if does_game_match_row:
                        self.create_individual_game(game, current_matchup, template, round)
                        while len(row) < 10:
                            row.append("")
                        row[9] = f"{API.GAME_URL}{game.link}"
                        # Need to remove games in case there are scenarios where two players get matched up twice (ie. 3 players per team)
                        current_matchup.games.remove(game)
                        break

        print(sheet_data)
        # Need a map from the link column depending on the players
        self.sheet.update_rows_raw(f"{sheet_name}!A1:J{121}", sheet_data)
        log_message(f"Updated the google sheet with {len(sheet_data)} new links", "patch_broken_2v2_games")