# WZ Nations Cup Scripts

This project contains a collection of CLI commands for managing and running Nations Cup. This is intended to be run parallel with a Google Sheets, specifically requiring specific formatting as input to the `cmatches` command (whereupon, the input/output can be chained for further commands).

Commands include managing matchup creation between teams, creating warzone games, processing created games and posting finished games to discord.

## Setup

The project uses python 3.10. To install and run the project, use the following:

1. Create a venv or use pyenv ot create a 3.10 instance.
2. Setup `config.json` with the appropriate values (use `config-example.json` for reference)
3. Setup `token.json` with the appropriate values (use `token-example.json` for reference)
4. To run the parse games check, use `run_parse_games.sh`
5. TO run the bot, use `run_bot_startup.sh`


## Usage

```bash
$ python main.py

usage: main.py [-h] [-r] [-e EMAIL] [-t TOKEN] [-s SPREADSHEET_ID] [-d DRYRUN]
               {cmatches,cgames,pgames,pplayers,setup,bot,validate} ...

Tool for running Nations Cup. Supports creating matchups for countries, starting &   
monitoring games through the WZ API and writing player results.

positional arguments:
  {cmatches,cgames,pgames,pplayers,setup,bot,validate}
                        Command to run
    cmatches            Create matches between teams
    cgames              Create Warzone games from matchups
    pgames              Parse games and update google sheets
    pplayers            Parse player stats and update google sheets
    setup               Create a setup config to avoid common parameters
    bot                 Initializes the discord bot and hourly job to post new game  
                        updates
    validate            Validates that players on teams can be invited to games on   
                        templates

options:
  -h, --help            show this help message and exit
  -r, --run             required for running the result for real. Otherwise dry-run  
                        is defaulted.
  -e EMAIL, --email EMAIL
                        Warzone email used for commands requiring the API. Not       
                        required for `setup`, `cmatches` and `pplayers`. Refer to    
                        `setup` for generating a config file.
  -t TOKEN, --token TOKEN
                        Warzone API token
                        (https://www.warzone.com/wiki/Get_API_Token_API) used for    
                        commands requiring the API. Not required for `setup`,        
                        `cmatches` and `pplayers`. Refer to `setup` for generating   
                        a config file.
  -s SPREADSHEET_ID, --spreadsheet_id SPREADSHEET_ID
                        Google Sheets Spreadsheet ID. This is the ID in the URL for  
                        the sheet.
  -d DRYRUN, --dryrun DRYRUN
                        run dry-run without creasting games

Created by JustinR17
```

## Creating Team Matchups (`cmatches`)

Given a google sheets tab containing a single list of teams with their respective players (player name in first column; player id in second column) as input, match up consecutive pairs of teams and generate random matches between players. There will be a total of 12 games created where players get 2 games if a team has 6 players, and 3 games if less.

The output will be written to a `RX Games` tab as specified in the arguments by round number.

**NOTE:** no warzone games will be created.

### Usage

```bash
$ python main.py cmatches -h
usage: main.py cmatches [-h] input output round

positional arguments:
  input       Input sheet tab name to read from
  output      Output sheet tab name
  round       Integer value specifying the round number

options:
  -h, --help  show this help message and exit
```

## Creating Warzone Games (`cgames`)

Given a `RX Games` google sheets tab containing the output from `cmatches`, generate Warzone games pertaining to the template argument input. Warzone game links will be posted to standard output, file & google sheets in the same tab.

### Usage

```bash
$ python main.py cgames -h
usage: main.py cgames [-h] sheet round template

positional arguments:
  sheet       Input sheet tab name to read from
  round       Round number
  template    Template ID

options:
  -h, --help  show this help message and exit
```

## Processing Warzone Games (`pgames`)

Iterates through google sheets tabs containing the signature `RX Games` where `X` is the round number. The command will iterate over all unfinished games, check for completed and update the google sheet as needed. If an open lobby game has not been accepted in 4 days, the game will be deleted and the following is used to determine the winner:

1. Assign win to left player if they have joined, or are invited and the right player declined
2. Assign win to the right player if they have joined, or are invited and the left player declined
3. Randomly assign win if both players are invited, or declined

The google sheets `RX Games` tabs will be updated with the country round scores in addition to player stats.

### Usage

```bash
$ python main.py pgames -h
usage: main.py pgames [-h]

options:
  -h, --help  show this help message and exit
```

## Running the Discord Bot (`bot`)

A blocking command that runs the Discord bot. The bot will check local files for newly finished games 5 minutes past every hour. New games found will be posted to the game log in the Nations Cup Discord.

There are additional commands for posting player (`pstats` & `pnstats`) & country statistics (`cstats`).

### Usage

```bash
$ python main.py bot -h
usage: main.py bot [-h]

options:
  -h, --help  show this help message and exit
```

## Validate Player Invite Statuses (`validate`)

Given the same input to `cmatches`, iterate through all players to test the ability to invite the player to games. This is used to ensure that all players can be invited to games (ensuring both that no players are blacklisted & that no player has locked template settings).

### Usage

```bash
$ python main.py validate -h
usage: main.py validate [-h] templates sheet

positional arguments:
  templates   Comma separated lists of templates
  sheet       Input sheet tab name to read from

options:
  -h, --help  show this help message and exit
```

## Setup Common Configs (`setup`)

Convenience command to create a config with warzone email, API token and google sheets ID to avoid needing to add this information on every call.

### Usage

```bash
$ python main.py setup -h
usage: main.py setup [-h]

options:
  -h, --help  show this help message and exit
```
