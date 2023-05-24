# Parse command-line arguments
import argparse
import os
import json

config = {}
if os.path.isfile("config.json"):
    config_file = open("config.json", "r")
    config = json.load(config_file)
    config_file.close()


parser = argparse.ArgumentParser(
    description="Tool for running Nations Cup. Supports creating matchups for countries, starting & monitoring games through the WZ API and writing player results.",
    allow_abbrev=True,
)
parser.add_argument(
    "-r",
    "--run",
    help="required for running the result for real. Otherwise dry-run is defaulted.",
    action="store_true",
)
parser.add_argument(
    "cmd", choices=["cmatches", "cgames", "pgames", "pplayers", "setup"]
)
parser.add_argument("-e", "--email")
parser.add_argument("-t", "--token")
args = parser.parse_args()
print(args)

if args.email is None and args.cmd in ["cgames", "pgames"]:
    parser.error("-e/--email is required if no config is present")
if args.token is None and args.cmd in ["cgames", "pgames"]:
    parser.error("-t/--token is required if no config is present")


if args.cmd == "setup":
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
