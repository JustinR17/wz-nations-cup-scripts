from collections import Counter
from itertools import permutations
import json
import os
from pprint import pprint
from random import shuffle
import re

from typing import Dict, List, Tuple
from NCTypes import GameResult, Matchup, Player, Team, TeamResult
from sheet import GoogleSheet
import jsonpickle

from utils import log_exception, log_message


class CreateMatches:

    def __init__(self, config):
        self.config = config
        self.sheet = GoogleSheet(config)

    def run(self, input_sheet_name: str, output_sheet_name: str, round: int, players_per_team: int):
        """
        Reads the google sheet with a list of teams. Creates matchups between countries and outputs to google sheets, a file & terminal output
        """
        try:
            log_message("Running CreateMatches", "CreateMatches.run")
            teams = self.parse_sheet_for_teams(input_sheet_name)
            
            # Did not want to mix up the flows too much so separated 1v1s and 2v2s
            if players_per_team == 1:
                matchups = self.create_team_matchups(teams)
                self.write_matchups(output_sheet_name, matchups, round)
            elif players_per_team == 2:
                matchups = self.create_2v2_team_matchups(teams)
                self.write_2v2_matchups(output_sheet_name, matchups, round)
            else:
                raise Exception(f"Invalid players_per_team argument provided: '{players_per_team}'")
        except Exception as e:
            log_exception(e)


    def parse_sheet_for_teams(self, sheet_name) -> List[Team]:
        teams: List[Team] = []
        sheet_rows = self.sheet.get_rows(f"{sheet_name}!A1:B300")

        current_team = None
        for row in sheet_rows:
            if not row:
                # Empty row (denotes the end of a team)
                current_team = None
            elif not current_team and row:
                # New team to add
                current_team = Team(row[0].strip())
                teams.append(current_team)
            elif row:
                # New player to add to team (need to regex capture the ID since warzone URLs are provided)
                current_team.players.append(Player(row[0].strip(), int(re.search(r'^.*?p=(\d*).*$', row[1]).group(1)), current_team))
        return teams

    def create_team_matchups(self, teams: List[Team]) -> List[Matchup]:
        """
        Given a list of teams (where consecutive pairs face each other), create unique matchups between players.

        Returns a list of team matchups.
        """

        matchups: List[Matchup] = []
        for i in range(0, len(teams), 2):
            extended_teams = [[], []]
            for j in range(12):
                # 12 players per team, but this can vary on how many games per player depending on team size
                extended_teams[0].append(teams[i].players[j%len(teams[i].players)])
                extended_teams[1].append(teams[i+1].players[j%len(teams[i+1].players)])

            # Since we just shuffle, it is possible for the pairings to be invalid. Must check this
            iterations = 1
            shuffle(extended_teams[0])
            shuffle(extended_teams[1])
            while not self.is_valid_matchup(extended_teams[0], extended_teams[1], len(teams[i].players) == 3 and len(teams[i+1].players) == 3) and iterations < 1000:
                iterations += 1
                shuffle(extended_teams[0])
                shuffle(extended_teams[1])
            
            if iterations == 1000:
                # This should not happen if the matchup was added correctly
                log_exception(f"Reached 1000 iterations while finding matchups for {teams[i].name} vs {teams[i+1].name}")
            
            matchups.append(Matchup(teams[i], teams[i+1]))
            matchups[-1].import_games_from_pairing_lists(extended_teams)
            
            log_message(f"{teams[i].name} vs. {teams[i+1].name} ({iterations} iterations)", "create_team_matchups")
            for game in matchups[-1].games:
                log_message(f"\t{game.players[0].name.encode()} vs. {game.players[1].name.encode()}", "create_team_matchups")
            log_message("", "create_team_matchups")
        return matchups

    def is_valid_matchup(self, team_a: List[Player], team_b: List[Player], minimum_teams: bool) -> bool:
        """
        Check if a shuffled list of teams is valid. This varies if both team has 3 players vs not.

        1. If both teams have 3 players (denoted by minimum_teams), then each player will have a duplicate game agaisnt 1 opponent only.
        2. If not, then not player should have a duplicate game against an opponent.

        Returns true if the matchup is valid.
        """
        seen_matches: Dict[str, List[str]] = {}


        for i in range(12):
            seen_matches.setdefault(team_a[i].id, []).append(team_b[i].id)
            seen_matches.setdefault(team_b[i].id, []).append(team_a[i].id)
        
        # Only when both teams have 3 should players get a duplicate game
        # Each player should only get one game that is duplicate (ie. cannot face only two people twice)
        for opps in seen_matches.values():
            # Only when both teams have 3 should players get a duplicate game
            # Each player should only get one game that is duplicate (ie. cannot face only two people twice)
            most_seen_matches = Counter(opps).most_common(2)
            if len(most_seen_matches) < 2 or most_seen_matches[0][1] > (2 if minimum_teams else 1) or most_seen_matches[1][1] > 1:
                return False
        
        return True

    def write_matchups(self, sheet_name: str, matchups: List[Matchup], round: str):
        """
        Output the matchups to a file for safety and to the google sheets
        """

        # Output to file first since this is safer
        with open(f"data/matchups_output_r{round}.json", "w", encoding="utf-8") as output_file:
            log_message("JSON version of matchups data is stored to 'matchups_output.json'", "write_matchups")
            json.dump(jsonpickle.encode(matchups), output_file)
        
        team_results: Dict[str, TeamResult] = {}
        player_results: Dict[str, GameResult] = {}
        if os.path.isfile("data/standings.json"):
            with open("data/standings.json", "r", encoding="utf-8") as input_file:
                results_input = jsonpickle.decode(json.load(input_file))
                team_results, player_results = results_input
        

        sheet_data: List[List[str]] = [[]]
        for matchup in matchups:
            sheet_data.append([matchup.teams[0].name, len(matchup.teams[0].players)-6, "vs.", matchup.teams[1].name, len(matchup.teams[1].players)-6])
            team_results.setdefault(matchup.teams[0].name, TeamResult(matchup.teams[0].name)).init_score(f"R{round}", matchup.teams[1].name, len(matchup.teams[0].players)-6, len(matchup.teams[1].players)-6)
            team_results.setdefault(matchup.teams[1].name, TeamResult(matchup.teams[1].name)).init_score(f"R{round}", matchup.teams[0].name, len(matchup.teams[1].players)-6, len(matchup.teams[0].players)-6)
            for game in matchup.games:
                sheet_data.append([game.players[0].name, game.players[0].id, "", game.players[1].name, game.players[1].id, game.link])
            sheet_data.append([]) # Empty row to divide teams
        self.sheet.update_rows_raw(f"{sheet_name}!A1:F{len(sheet_data)}", sheet_data)
        log_message(f"Updated google sheets with {len(sheet_data)} new rows", "write_matchups")

        pprint(team_results)
        pprint(player_results)
        with open(f"data/standings.json", "w", encoding="utf-8") as output_file:
            log_message("JSON version of standings data is stored to 'standings.json'", "write_matchups")
            json.dump(jsonpickle.encode((team_results, player_results)), output_file)
    



    #############################
    ######## 2v2 VERSION ########
    #############################

    def create_2v2_team_matchups(self, teams: List[Team]) -> List[Matchup]:
        """
        Given a list of teams (where consecutive pairs face each other), create unique matchups between players.

        Returns a list of team matchups.
        """

        matchups: List[Matchup] = []
        for i in range(0, len(teams), 2):
            team_permutations = [
                list(permutations(teams[i].players, 2)),
                list(permutations(teams[i+1].players, 2))
            ]

            # First step is to get the pairs on each team
            extended_teams: List[List[Tuple[Player, Player]]] = [[], []]
            for idx, tps in enumerate(team_permutations):
                if len(teams[i+idx].players) == 3:
                    # There will be duplicates. 3 games each
                    extended_teams[idx] += team_permutations[idx] + team_permutations[idx]
                else:
                    copy_tp: List[Tuple[Player, Player]] = tps.copy()
                    # No duplications, but possibly 3 games
                    # Number of individual games
                    individual_games: Dict[str, int] = {}
                    extra_game_player_selected = False
                    for tp in copy_tp:
                        if individual_games.get(tp[0].id, 0) < (3 if len(teams[i+idx].players) == 4 else 2) and individual_games.get(tp[1].id, 0) < (3 if len(teams[i+idx].players) == 4 else 2):
                            # valid matchup
                            extended_teams[idx].append(tp)
                            individual_games[tp[0].id] = individual_games.get(tp[0].id, 0) + 1
                            individual_games[tp[1].id] = individual_games.get(tp[1].id, 0) + 1
                        elif len(teams[i+idx].players) == 5 and not extra_game_player_selected and \
                                ((individual_games.get(tp[0].id, 0) == 2 and individual_games.get(tp[1].id, 0) < 2) or \
                                    (individual_games.get(tp[0].id, 0) < 2 and individual_games.get(tp[1].id, 0) == 2)):
                            # valid matchup, extra game for 1 player has been added
                            extended_teams[idx].append(tp)
                            individual_games[tp[0].id] = individual_games.get(tp[0].id, 0) + 1
                            individual_games[tp[1].id] = individual_games.get(tp[1].id, 0) + 1
                            extra_game_player_selected = True
                        if len(extended_teams[idx]) == 6:
                            break
                
            # Second step is to shuffle both lists and match 
            # Since we just shuffle, it is possible for the pairings to be invalid. Must check this
            iterations = 1
            shuffle(extended_teams[0])
            shuffle(extended_teams[1])
            while not self.is_valid_2v2_matchup(extended_teams[0], extended_teams[1]) and iterations < 1000:
                iterations += 1
                shuffle(extended_teams[0])
                shuffle(extended_teams[1])
            
            if iterations == 1000:
                # This should not happen if the matchup was added correctly
                log_exception(f"Reached 1000 iterations while finding matchups for {teams[i].name} vs {teams[i+1].name}")
            
            matchups.append(Matchup(teams[i], teams[i+1]))
            matchups[-1].import_2v2_games_from_pairing_lists(extended_teams)
            
            log_message(f"{teams[i].name} vs. {teams[i+1].name} ({iterations} iterations)", "create_team_matchups")
            for game in matchups[-1].games:
                log_message(f"\t{game}", "create_team_matchups")
            log_message("", "create_team_matchups")
        return matchups

    def is_valid_2v2_matchup(self, team_a: List[Tuple[Player, Player]], team_b: List[Tuple[Player, Player]]) -> bool:
        """
        Check if a shuffled list of teams is valid.
        
        Returns true if the matchup is valid.
        """
        seen_matches: Dict[str, List[str]] = {}


        for i in range(6):
            seen_matches.setdefault((team_a[i][0].id, team_a[i][1].id), []).append((team_b[i][0].id, team_b[i][1].id))
            seen_matches.setdefault((team_b[i][0].id, team_b[i][1].id), []).append((team_a[i][0].id, team_a[i][1].id))
        
        for opps in seen_matches.values():
            # Since there are more possible permutations, there is no need to worry about duplicate games (with exactly same teams)
            most_seen_matches = Counter(opps).most_common(1)
            if len(most_seen_matches) < 1 or most_seen_matches[0][1] > 1:
                return False
        
        return True

    def write_2v2_matchups(self, sheet_name: str, matchups: List[Matchup], round: str):
        """
        Output the matchups to a file for safety and to the google sheets
        """

        # Output to file first since this is safer
        with open(f"data/matchups_output_r{round}.json", "w", encoding="utf-8") as output_file:
            log_message("JSON version of matchups data is stored to 'matchups_output.json'", "write_matchups")
            json.dump(jsonpickle.encode(matchups), output_file)
        
        team_results: Dict[str, TeamResult] = {}
        player_results: Dict[str, GameResult] = {}
        if os.path.isfile("data/standings.json"):
            with open("data/standings.json", "r", encoding="utf-8") as input_file:
                results_input = jsonpickle.decode(json.load(input_file))
                team_results, player_results = results_input
        

        sheet_data: List[List[str]] = [[]]
        for matchup in matchups:
            sheet_data.append([matchup.teams[0].name, len(matchup.teams[0].players)-6, "vs.", matchup.teams[1].name, len(matchup.teams[1].players)-6])
            team_results.setdefault(matchup.teams[0].name, TeamResult(matchup.teams[0].name)).init_score(f"R{round}", matchup.teams[1].name, len(matchup.teams[0].players)-6, len(matchup.teams[1].players)-6)
            team_results.setdefault(matchup.teams[1].name, TeamResult(matchup.teams[1].name)).init_score(f"R{round}", matchup.teams[0].name, len(matchup.teams[1].players)-6, len(matchup.teams[0].players)-6)
            for game in matchup.games:
                sheet_data.append([game.players[0].name, game.players[0].id, game.players[1].name, game.players[1].id, "", game.players[2].name, game.players[2].id, game.players[3].name, game.players[3].id, game.link])
            sheet_data.append([]) # Empty row to divide teams
        self.sheet.update_rows_raw(f"{sheet_name}!A1:F{len(sheet_data)}", sheet_data)
        log_message(f"Updated google sheets with {len(sheet_data)} new rows", "write_matchups")

        pprint(team_results)
        pprint(player_results)
        with open(f"data/standings.json", "w", encoding="utf-8") as output_file:
            log_message("JSON version of standings data is stored to 'standings.json'", "write_matchups")
            json.dump(jsonpickle.encode((team_results, player_results)), output_file)
