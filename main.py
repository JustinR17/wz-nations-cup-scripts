# Parse command-line arguments
import argparse
import os
import json
from CreateGames import CreateGames

from CreateMatches import CreateMatches
from ParseGames import ParseGames
from ParsePlayers import ParsePlayers
from api import API

config = {"email": None, "token": None}
if os.path.isfile("config.json"):
    config_file = open("config.json", "r")
    config = json.load(config_file)
    config_file.close()


parser = argparse.ArgumentParser(
    description="Tool for running Nations Cup. Supports creating matchups for countries, starting & monitoring games through the WZ API and writing player results.",
    allow_abbrev=True,
    epilog="Created by JustinR17"
)
parser.add_argument(
    "-r",
    "--run",
    help="required for running the result for real. Otherwise dry-run is defaulted.",
    action="store_true",
)
parser.add_argument(
    "cmd", choices=["cmatches", "cgames", "pgames", "pplayers", "setup"], help="Nations cup command."
)
parser.add_argument("-e", "--email", help="Warzone email used for commands requiring the API. Not required for `setup`, `cmatches` and `pplayers`. Refer to `setup` for generating a config file.")
parser.add_argument("-t", "--token", help="Warzone API token (https://www.warzone.com/wiki/Get_API_Token_API) used for commands requiring the API. Not required for `setup`, `cmatches` and `pplayers`. Refer to `setup` for generating a config file.")
args = parser.parse_args()
print(args)

if args.email:
    config["email"] = args.email
if args.token:
    config["token"] = args.token

if config["email"] is None and args.cmd in ["cgames", "pgames"]:
    parser.error("-e/--email is required if no config is present")
if config["token"] is None and args.cmd in ["cgames", "pgames"]:
    parser.error("-t/--token is required if no config is present")

config["run"] = args.run

if args.cmd == "cmatches":
    create_matches = CreateMatches(config)
elif args.cmd == "cgames":
    create_games = CreateGames(config)
    print(API(config).check_game(25876595))
    print(API(config).validate_player_template_access(1277277659, ["342040","342041","342042","342043"]))
elif args.cmd == "pgames":
    parse_games = ParseGames(config)
elif args.cmd == "pplayers":
    parse_players = ParsePlayers(config)
elif args.cmd == "setup":
    print(
        f"Running setup to create a config.json file locally. This will allow you to run commands without needing to input the warzone email and API token every time. Note that everything is stored locally and no data is sent anywhere."
    )
    config["email"] = input("What is your Warzone Email? ")
    config["token"] = input(
        "What is your Warzone API Token? (https://www.warzone.com/wiki/Get_API_Token_API) "
    )
    print(f"Writing the following to 'config.json'\n{config}")

    config_file = open("config.json", "w")
    json.dump(config, config_file)
    config_file.close()
else:
    # Should not occur due to argparse library
    raise f"Unknown command supplied: '{args.cmd}'"
