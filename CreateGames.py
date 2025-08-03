from datetime import datetime
import re
from NCTypes import Game, Matchup, Player, Team
from api import API
from data import NO_GAME_PLAYED, TAB_TO_GAME_RANGE_MAPPING, CGAMES_TAB_TO_TABLE_RANGE_MAPPING, UNKNOWN_PLAYER_NAME
from sheet import GoogleSheet

from utils import log_exception, log_message

"""
DICITONARY SCHEMA

team_standings: Dict[str, TeamResult]
{
    team_id: {
        name: str,
        games_results: {
            "round-group": {
                opp: str,
                wins: int,
                losses: int,
                modifier_for: int,
                modifier_against: int,
                games: List[str]
            }
        }
    }
}


player_standings: Dict[str, PlayerResult]
{
    player_id: {
        name: str,
        id: str,
        team: str,
        wins: int,
        losses: int,
    },
    "12312312": {
        name: "JustinR17",
        id: "12312312",
        team: "CAN",
        wins: 6,
        losses: 1,
    },
}

game_results: Dict[str, WarzoneGame]
{
    game_id: {
        winner: {
            player_name: str,
            player_id: str,
            clan: str,
        },
        loser: {
            player_name: str,
            player_id: str,
            clan: str,
        },
        created_date: str,
        finished_date: str,
        reason: GameOutcome,
        turns: int,
    }
}

"""


class CreateGames:

    def __init__(self, config):
        self.config = config
        self.sheet = GoogleSheet(config)
        self.api = API(config)

    def run(self):
        """
        Reads the sheet_name matchups and creates games. The sheet will be updated with the game links
        """
        try:
            log_message("Running CreateGames", "CreateGames.run")
            tabs = self.sheet.get_tabs_by_status([GoogleSheet.TabStatus.GAME_CREATION])
            log_message(
                f"Found the following templates to create games on: {tabs}",
                "CreateGames.run",
            )

            # Create games for each row missing links
            for tab in tabs:
                self.initialize_game_matchups(tab)
        except Exception as e:
            log_exception(e)

    def initialize_game_matchups(
        self,
        tab: str,
    ):
        tab_phase = re.search("^(_\w+)", tab).group(1)
        tab_status = self.sheet.get_rows(f"{tab}!A1:B1")
        game_range = TAB_TO_GAME_RANGE_MAPPING[tab_phase]
        table_range = CGAMES_TAB_TO_TABLE_RANGE_MAPPING[tab_phase]
        round = tab[1:]

        tab_rows_values = self.sheet.get_rows(f"{tab}!{game_range}")
        table_rows_values = (
            self.sheet.get_rows(f"{tab}!{table_range}") if table_range else []
        )

        # parse the games to be made
        group, team_a, team_b = "", "", ""
        for i, row in enumerate(tab_rows_values):
            row.extend("" for _ in range(9 - len(row)))
            if row[0]:
                # Update group and team values
                group, team_a, team_b = row[0], row[1], row[4]
                if row[6] != "done":
                    row.extend("" for _ in range(7 - len(row)))
                    row[6] = "done"
                log_message(
                    f"Checking games for {round}-{group}-{team_b}: {team_a} vs. {team_b}",
                    "initialize_game_matchups",
                )
                continue
            elif not row[1]:
                continue

            if (
                row[1].strip() == UNKNOWN_PLAYER_NAME
                or row[4].strip() == UNKNOWN_PLAYER_NAME
            ):
                # one of the  teams does not have enough players. forfeit and do notcreate any game
                row[3] = NO_GAME_PLAYED
                continue

            if row[8]:
                print(f"\tChanging the template on line {i} to: {row[8]}")
                template = row[8].strip()
            # parse new game
            player_a = Player(
                row[1].strip(),
                int(re.search(r"^.*?p=(\d*).*$", row[2]).group(1)),
                Team(team_a),
            )
            player_b = Player(
                row[4].strip(),
                int(re.search(r"^.*?p=(\d*).*$", row[5] or 0).group(1)),
                Team(team_b),
            )

            if not row[6]:
                # game does not exist yet
                game = Game([player_a, player_b], Game.Outcome.UNDEFINED, row[6])
                self.create_games(
                    game,
                    f"{round} - {group}",
                    template,
                )
                row[6] = f"https://www.warzone.com/MultiPlayer?GameID={game.link}"
        self.sheet.update_rows_raw(f"{tab}!{game_range}", tab_rows_values)
        if len(tab_status[0]) < 2:
            tab_status[0].append(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        else:
            # Overwrite previous value
            tab_status[0][1] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.sheet.update_rows_raw(f"{tab}!A1:B1", tab_status)

    def create_games(self, game: Game, round: str, template: str):
        title = f"Nations' Cup 2025 {round}"
        description = f"""This game is a part of the Nations' Cup 2025 {round}, run by Rento. You have 3 days to join the game.
            
Match is between:
\t{game.players[0].name.encode()} in {game.players[0].team.name}
\t{game.players[1].name.encode()} in {game.players[1].team.name}

https://docs.google.com/spreadsheets/d/1kv2E-WfMKo4-YqkdHAqvOHMaXN1h94S4vOONnN-hYEs
"""

        try:
            game_link = self.api.create_game(
                [
                    (game.players[0].id, game.players[0].team.name),
                    (game.players[1].id, game.players[1].team.name),
                ],
                template,
                title,
                description,
            )

            if game_link:
                log_message(
                    f"\tGame created between {game.players[0].name.encode()} & {game.players[1].name.encode()} - {game_link}",
                    "create_games",
                )
                game.link = game_link
        except API.GameCreationException as e:
            log_exception(
                f"\tGameCreationException: Unable to create game between {game.players[0].name.encode()} & {game.players[1].name.encode()}: '{str(e)}'"
            )
        except Exception as e:
            log_exception(
                f"\tUnknown Exception: Unable to create game between {game.players[0].name.encode()} & {game.players[1].name.encode()}: '{str(e)}'"
            )

    #############################
    ########### PATCH ###########
    #############################

    def create_individual_game(
        self, game: Game, matchup: Matchup, template: str, round: int
    ):
        title = f"Nations' Cup 2023 R{round} {matchup.teams[0].name} vs. {matchup.teams[1].name}"
        players_by_team = game.get_player_names_by_team()
        description = f"""This game is a part of the Nations' Cup R{round}, run by Marcus. You have 3 days to join the game.
        
Match is between:
\t{", ".join(players_by_team[matchup.teams[0].name]).encode()} in {matchup.teams[0].name}
\t{", ".join(players_by_team[matchup.teams[1].name]).encode()} in {matchup.teams[1].name}

https://docs.google.com/spreadsheets/d/1QPKGgwToBd2prap8u3XVUx9F47SuvMH9wJruvG0t2D4
"""

        try:
            game_link = self.api.create_game(
                list(map(lambda e: (e.id, e.team.name), game.players)),
                template,
                title,
                description,
            )
            if game_link:
                log_message(
                    f"\tGame created between {game} - {game_link}", "create_2v2_games"
                )
                game.link = game_link
        except API.GameCreationException as e:
            log_exception(
                f"\tGameCreationException: Unable to create game between {game.players[0].name.encode()} & {game.players[1].name.encode()}: '{str(e)}'"
            )
        except Exception as e:
            log_exception(
                f"\tUnknown Exception: Unable to create game between {game.players[0].name.encode()} & {game.players[1].name.encode()}: '{str(e)}'"
            )
