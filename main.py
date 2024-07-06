# Parse command-line arguments
import argparse
import os
import json
import sys

import jsonpickle
from CreateGames import CreateGames

# from CreateMatches import CreateMatches
# from GetFunStats import GetFunStats
from ParseGames import ParseGames

# from ParsePlayers import ParsePlayers
from ValidatePlayers import ValidatePlayers

# from ValidateResults import ValidateResults
from bot import NationsCupBot
from sheet import GoogleSheet
from test import TestCommand

config = {"email": None, "token": None, "spreadsheet_id": None}
if os.path.isfile("config.json"):
    config_file = open("config.json", "r")
    config = json.load(config_file)
    config_file.close()

jsonpickle.set_encoder_options("json", indent=4)


parser = argparse.ArgumentParser(
    description="Tool for running Nations Cup. Supports creating matchups for countries, starting & monitoring games through the WZ API and writing player results.",
    allow_abbrev=True,
    epilog="Created by JustinR17",
)
parser.add_argument(
    "-r",
    "--run",
    help="required for running the result for real. Otherwise dry-run is defaulted.",
    action="store_true",
)
subparsers = parser.add_subparsers(help="Command to run", dest="cmd")

test = subparsers.add_parser("test", help="Testing ground for new commands")
cmatches = subparsers.add_parser("cmatches", help="Create matches between teams")
cmatches.add_argument("input", help="Input sheet tab name to read from")
cmatches.add_argument("output", help="Output sheet tab name")
cmatches.add_argument("round", help="Integer value specifying the round number")
cmatches.add_argument(
    "players", type=int, help="Integer value specifying the number of players per team"
)

cgames = subparsers.add_parser("cgames", help="Create Warzone games from matchups")

pgames = subparsers.add_parser("pgames", help="Parse games and update google sheets")
validate_results = subparsers.add_parser(
    "validate_results", help="Validates player/team scores by parsing games again"
)
pplayers = subparsers.add_parser(
    "pplayers", help="Parse player stats and update google sheets"
)
setup = subparsers.add_parser(
    "setup", help="Create a setup config to avoid common parameters"
)
bot = subparsers.add_parser(
    "bot", help="Initializes the discord bot and hourly job to post new game updates"
)

validate = subparsers.add_parser(
    "validate",
    help="Validates that players on teams can be invited to games on templates",
)

funstats = subparsers.add_parser(
    "funstats", help="aggregates all games and outputs stats to a file"
)

parser.add_argument(
    "-e",
    "--email",
    help="Warzone email used for commands requiring the API. Not required for `setup`, `cmatches` and `pplayers`. Refer to `setup` for generating a config file.",
)
parser.add_argument(
    "-t",
    "--token",
    help="Warzone API token (https://www.warzone.com/wiki/Get_API_Token_API) used for commands requiring the API. Not required for `setup`, `cmatches` and `pplayers`. Refer to `setup` for generating a config file.",
)
parser.add_argument(
    "-s",
    "--spreadsheet_id",
    help="Google Sheets Spreadsheet ID. This is the ID in the URL for the sheet.",
)
parser.add_argument(
    "-d", "--dryrun", action="store_true", help="run dry-run without creasting games"
)
args = parser.parse_args()
print(args)

if args.email:
    config["email"] = args.email
if args.token:
    config["token"] = args.token
config["dryrun"] = args.dryrun

if config["email"] is None and args.cmd in ["cgames", "pgames"]:
    parser.error("-e/--email is required if no config is present")
if config["token"] is None and args.cmd in ["cgames", "pgames"]:
    parser.error("-t/--token is required if no config is present")
if config["spreadsheet_id"] is None and args.cmd in [
    "cmatches",
    "cgames",
    "pgames",
    "pplayers",
]:
    parser.error("-s/--spreadsheet_id is required if no config is present")

config["run"] = args.run

# ns = GoogleSheet(config)
# print(ns.get_sheet_tabs_data())
# print(ns.get_rows("Player_Stats!A1:E200"))
# sys.exit(0)

if args.cmd == "cgames":
    create_games = CreateGames(config)
    create_games.run()
elif args.cmd == "pgames":
    parse_games = ParseGames(config)
    parse_games.run()
elif args.cmd == "setup":
    print(
        f"Running setup to create a config.json file locally. This will allow you to run commands without needing to input the warzone email and API token every time. Note that everything is stored locally and no data is sent anywhere."
    )
    config["email"] = input("What is your Warzone Email? ")
    config["token"] = input(
        "What is your Warzone API Token? (https://www.warzone.com/wiki/Get_API_Token_API) "
    )
    config["spreadsheet_id"] = input(
        "What is the spreadsheet ID of the Google Sheets? (The ID in the URL) "
    )
    print(f"Writing the following to 'config.json'\n{config}")

    config_file = open("config.json", "w")
    json.dump(config, config_file)
    config_file.close()
elif args.cmd == "bot":
    bot = NationsCupBot(config=config)
    bot.run(config["discord_token"])
elif args.cmd == "validate":
    validate_players = ValidatePlayers(config)
    validate_players.run()
elif args.cmd == "validate_results":
    validate_results = ValidateResults(config)
    validate_results.run()
elif args.cmd == "funstats":
    fun_stats = GetFunStats(config)
    fun_stats.run()
elif args.cmd == "test":
    test = TestCommand(config)
    test.run()
else:
    # Should not occur due to argparse library
    raise f"Unknown command supplied: '{args.cmd}'"
