import os
from typing import Any, Dict, List
import discord
import sys
import json
from discord.flags import Intents
import jsonpickle
import requests
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import socket
from dotenv import load_dotenv
from datetime import datetime
import traceback
import random
import subprocess

from NCTypes import WarzoneGame
from utils import log_exception, log_message

intents = discord.Intents.default()
intents.members = True
intents.messages = True
client = discord.Client(intents=intents)


ROUND_TO_TEMPLATE = {
    "R1": "Test",
    "R2": "",
    "R3": "",
    "R4": "",
    "R5": "",
}

class NationsCupBot(discord.Client):

    def __init__(self, *, config: Dict, **options: Any) -> None:
        super().__init__(intents=intents, **options)
        self.config = config
        self.jobs_scheduled = False

    async def post_game_updates_job(self):
        """
        Read the buffer newly finished game file and post games to discord. Clears the buffer file after completion.
        """

        # Post the games that have finished since the last time we checked
        log_message("Running post_game_updates_job", "bot")
        with open (f"data/newly_finished_games.json", "r", encoding="utf-8") as input_file:
            buffer_newly_finished_games: Dict[str, List[WarzoneGame]] = jsonpickle.decode(json.load(input_file))
            
            discord_channel = self.get_channel(int(self.config["game_log_channel"]))
            successfully_posted, total = 0, 0
            for round, games in buffer_newly_finished_games.items():
                for game in games:
                    total += 1
                    try:
                        if game.winner == game.players[0].id:
                            winner_name, winner_team = game.players[0].name, game.players[0].team
                            loser_name, loser_team = game.players[1].name, game.players[1].team
                        else:
                            winner_name, winner_team = game.players[1].name, game.players[1].team
                            loser_name, loser_team = game.players[0].name, game.players[0].team
                        embed = discord.Embed(
                            title=f"**{winner_team}** {winner_name} defeats **{loser_team}** {loser_name}",
                            description=f"[Game Link]({game.link})"
                        )
                        embed.add_field(name=round[0:2], value=ROUND_TO_TEMPLATE[round[0:2]])
                        await discord_channel.send(embed=embed)
                        successfully_posted += 1
                    except Exception as e:
                        log_exception(f"Error while handling game {game.link}: {e}")
        log_message(f"Successfully outputted {successfully_posted} of {total} game updates")
            
        if successfully_posted:
            with open (f"data/newly_finished_games.json", "w", encoding="utf-8") as output_file:
                # Reset the buffer file
                log_message("Resetting the buffer file after posting game updates", "bot")
                json.dump({}, output_file)

    async def on_ready(self):
        # Start schedulers (only on first run)
        if not self.jobs_scheduled:
            log_message("Scheduled post_game_updates_job", "bot")
            scheduler = AsyncIOScheduler()
            scheduler.add_job(self.post_game_updates_job, CronTrigger(hour="*", minute="5", second="0"))
            scheduler.start()
            self.jobs_scheduled = True
