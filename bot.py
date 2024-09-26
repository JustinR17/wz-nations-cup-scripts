from datetime import datetime
import os
from time import sleep
from typing import Any, Dict, List, Tuple
import discord
import json
from discord.ext import commands
import jsonpickle
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from discord import app_commands
import os

from NCTypes import PlayerResult, TableTeamResult, TeamResult, WarzoneGame
from utils import log_exception, log_message

intents = discord.Intents.default()
intents.members = True
intents.messages = True
intents.message_content = True
client = discord.Client(intents=intents)


ROUND_TO_TEMPLATE = {
    "Qualifiers R1": "Guiroma",
    "Qualifiers R2": "French Brawl",
    "Main R1": "Strategic MME",
    "Main R2": "Africa Ultima",
    "Main R3": "Numenor",
    "Main R4": "Volcano Island",
    "Main R5": "Biomes",
}

# Reverse ROY G BIV; Finals is all gold
ROUND_TO_COLOUR = {
    "Qualifiers": discord.Colour.from_rgb(148, 9, 211),
    "Qualifiers R1": discord.Colour.from_rgb(148, 9, 211),
    "Qualifiers R2": discord.Colour.from_rgb(75, 0, 130),
    "Main": discord.Colour.from_rgb(0, 0, 255),
    "Main R1": discord.Colour.from_rgb(0, 0, 255),
    "Main R2": discord.Colour.from_rgb(0, 255, 0),
    "Main R3": discord.Colour.from_rgb(255, 255, 0),
    "Main R4": discord.Colour.from_rgb(255, 127, 0),
    "Main R5": discord.Colour.from_rgb(255, 0, 0),
    "Finals": discord.Colour.gold(),
}

ROUND_TO_EMBED = {
    "Qualifiers": 1264965867419074611,
    "Main": 1271678678048444578,
    "Finals": 0,
}


class NCComands(commands.Cog):

    def __init__(self, bot: 'NationsCupBot') -> None:
        self.bot = bot

    @app_commands.command(
        name="create_embeds", description="creates new embed posts for phase scores"
    )
    async def create_embeds(self, interaction: discord.Interaction):
        if interaction.user.id != 162968893177069568:
            await interaction.response.send_message("Only Justin can use this command")
            return

        if not os.path.isfile("data/team_standings.json"):
            await interaction.response.send_message("No team standings file exists yet")
            return

        with open("data/team_standings.json", "r", encoding="utf-8") as input_file:
            team_standings: Dict[str, TableTeamResult] = jsonpickle.decode(
                json.load(input_file)
            )

        discord_channel = self.bot.get_channel(int(self.bot.config["score_channel"]))
        for phase, id in ROUND_TO_EMBED.items():
            if id == 0:
                # Need to create embed if standings exist:
                phase_standings = [
                    ps for ps in team_standings.items() if phase in ps[0]
                ]

                if len(phase_standings):
                    group_standings: Dict[str, List[TableTeamResult]] = {}
                    for key, team_result in phase_standings:
                        group_standings.setdefault(key.split("-")[1], []).append(
                            team_result
                        )

                    # new embed
                    embed = discord.Embed(
                        title=phase,
                        description="Scores are shown as:\n```team | Pts | MP```",
                        colour=ROUND_TO_COLOUR[phase],
                    )
                    for i, (group, team_results) in enumerate(group_standings.items()):
                        if phase == "Main" and i % 2 == 0 and i != 0:
                            embed.add_field(
                                name='\u200b',
                                value='\u200b',
                                inline=True,
                            )
                        if phase == "Qualifiers":
                            total_games = (len(set([result.team for result in team_results]))-1)*6*2
                        else:
                            total_games = 60
                        team_scores: Dict[str, Tuple[str, float, float]] = {}
                        for result in team_results:
                            if result.team not in team_scores:
                                # team_scores[result.team] = (result.team, result.wins_adjusted, result.wins, result.losses, result.wins+result.losses)
                                team_scores[result.team] = (result.team, result.wins_adjusted, result.wins_adjusted-result.wins-result.losses+total_games)
                            else:
                                scores = team_scores[result.team]
                                # team_scores[result.team] = (scores[0], scores[1]+result.wins_adjusted, scores[2]+result.wins, scores[3]+result.losses, scores[4]+result.wins+result.losses)
                                team_scores[result.team] = (scores[0], scores[1]+result.wins_adjusted, scores[2]+result.wins_adjusted-result.wins-result.losses)
                        team_scores_list = list(team_scores.values())
                        team_scores_list.sort(
                            key=lambda e: (e[1], e[2]), reverse=True
                        )

                        team_results_str = "\n".join(
                                [
                                    f"{e[0]:5}|{e[1]:4g}|{e[2]:4g}"
                                    for e in team_scores_list
                                ]
                            )
                        embed.add_field(
                            name=group,
                            value=f"```{team_results_str}```"[0:1024],
                            inline=True,
                        )
                    embed.add_field(name='\u200b', value='\u200b')
                    embed.timestamp = datetime.now()
                    sent_embed = await discord_channel.send(embed=embed)
        await interaction.channel.send('')

    @app_commands.command(name="link", description="returns the google sheets link")
    async def link(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            "<https://docs.google.com/spreadsheets/d/1R7VDKXYN3ofo5xBkPQ_XOmcCCmb1W2w_kHXCO2qy_Xs>"
        )

    @app_commands.command(name="kill", description="justin only command")
    async def kill(self, interaction: discord.Interaction):
        if (
            interaction.user.id == 162968893177069568
            or interaction.user.id == 281740561885691904
        ):  # my id + rento
            await interaction.response.send_message("Killing the bot")
            os.system("sudo shutdown -h now")
        else:
            await interaction.response.send_message("Only Justin can use this command")

    @commands.command(name="sync")
    async def sync(self, ctx):
        synced = await self.bot.tree.sync()
        print(f"Synced {len(synced)} command(s).")
        await ctx.send(f"Synced {len(synced)} command(s).")

    @commands.command(name="reboot")
    async def reboot(self, ctx):
        await ctx.send("Restarting rpi")
        os.system("sudo shutdown -r now")

    @commands.command(name="msg")
    async def msg(self, ctx: commands.Context, channel: str, *msg):
        if ctx.author.id == 162968893177069568:
            dc = self.bot.get_channel(int(channel))
            await dc.send(" ".join(msg))


class NationsCupBot(commands.Bot):

    def __init__(self, *, config: Dict, **options: Any) -> None:
        super().__init__(command_prefix="nc!", intents=intents, **options)
        self.config = config
        self.jobs_scheduled = False

    async def post_game_updates_job(self):
        """
        Read the buffer newly finished game file and post games to discord. Clears the buffer file after completion.
        """

        # Post the games that have finished since the last time we checked
        log_message("Running post_game_updates_job", "bot")
        with open(
            f"data/newly_finished_games.json", "r", encoding="utf-8"
        ) as input_file:
            buffer_newly_finished_games: Dict[str, List[WarzoneGame]] = (
                jsonpickle.decode(json.load(input_file))
            )

            discord_channel = self.get_channel(int(self.config["game_log_channel"]))
            successfully_posted, total = 0, 0
            for key, games in buffer_newly_finished_games.items():
                print(f"{len(games)} games in {key} to post")
                round, group = key.split("-")
                for game in games:
                    total += 1
                    try:
                        winners = [x for x in game.players if x.id in game.winner]
                        losers = [x for x in game.players if x.id not in game.winner]
                        log_message(f"GAME: {game}", "post_game_updates_job")
                        print(winners)
                        print(losers)
                        embed = discord.Embed(
                            title=f"{', '.join([p.name for p in winners])} defeats {', '.join([p.name for p in losers])}"[
                                0:256
                            ],
                            description=f"[Game Link]({game.link})"[0:4096],
                            colour=ROUND_TO_COLOUR[round],
                        )
                        embed.add_field(
                            name=f"{round} {ROUND_TO_TEMPLATE[round]} - {group}"[0:256],
                            value=f"**{winners[0].team}** ({winners[0].score:g} pts) defeats **{losers[0].team}** ({losers[0].score:g} pts)"[0:1024],
                        )
                        # embed.set_footer(
                        #     text=f"{winners[0].team} {winners[0].score:g} - {losers[0].team} {losers[0].score:g}"[
                        #         0:2048
                        #     ]
                        # )
                        sent_embed = await discord_channel.send(embed=embed)

                        if "CAN" in winners[0].team:
                            await sent_embed.add_reaction("🇨🇦")
                            await sent_embed.add_reaction("🎉")
                            # await sent_embed.add_reaction("🇨")
                            # await sent_embed.add_reaction("🇦")
                            # await sent_embed.add_reaction("🇳")
                            # await sent_embed.add_reaction("🍁")
                            # await sent_embed.add_reaction("🦫")
                        successfully_posted += 1
                    except Exception as e:
                        log_exception(f"Error while handling game {game.link}: {e}")
        # Update embeds now:
        with open("data/team_standings.json", "r", encoding="utf-8") as input_file:
            team_standings: Dict[str, TableTeamResult] = jsonpickle.decode(
                json.load(input_file)
            )

            discord_channel = self.get_channel(int(self.config["score_channel"]))
            for phase, embed in ROUND_TO_EMBED.items():
                if embed != 0:
                    group_standings: Dict[str, List[TableTeamResult]] = {}
                    phase_standings = [
                        ps for ps in team_standings.items() if phase in ps[0]
                    ]
                    for key, team_result in phase_standings:
                        group_standings.setdefault(key.split("-")[1], []).append(
                            team_result
                        )

                    message = await discord_channel.fetch_message(embed)
                    embed = message.embeds[0]
                    # embed.description = "Scores are shown as:\n```Team | Pts | MP```"
                    embed.clear_fields()
                    for i, (group, team_results) in enumerate(group_standings.items()):
                        if phase == "Main" and i % 2 == 0 and i != 0:
                            embed.add_field(
                                name='\u200b',
                                value='\u200b',
                                inline=True,
                            )
                        if phase == "Qualifiers":
                            total_games = (len(set([result.team for result in team_results]))-1)*6*2
                        else:
                            total_games = 60
                        team_scores: Dict[str, Tuple[str, float, float]] = {}
                        for result in team_results:
                            if result.team not in team_scores:
                                # team_scores[result.team] = (result.team, result.wins_adjusted, result.wins, result.losses, result.wins+result.losses)
                                team_scores[result.team] = (result.team, result.wins_adjusted, result.wins_adjusted-result.wins-result.losses+total_games)
                            else:
                                scores = team_scores[result.team]
                                # team_scores[result.team] = (scores[0], scores[1]+result.wins_adjusted, scores[2]+result.wins, scores[3]+result.losses, scores[4]+result.wins+result.losses)
                                team_scores[result.team] = (scores[0], scores[1]+result.wins_adjusted, scores[2]+result.wins_adjusted-result.wins-result.losses)
                        team_scores_list = list(team_scores.values())
                        team_scores_list.sort(
                            key=lambda e: (e[1], e[2]), reverse=True
                        )

                        if phase == "Qualifiers":
                            team_results_str = "\n".join(
                                    [
                                        f"{e[0]:5}|{e[1]:4g}|{e[2]:4g}"
                                        for e in team_scores_list
                                    ]
                                )
                        else:
                            team_results_str = "\n".join(
                                    [
                                        f"{e[0]:5} | {e[1]:2g} | {e[2]:2g}"
                                        for e in team_scores_list
                                    ]
                                )
                        embed.add_field(
                            name=group,
                            value=f"```{team_results_str}```"[0:1024],
                            inline=True,
                        )
                    embed.add_field(name='\u200b', value='\u200b')
                    embed.timestamp = datetime.now()
                    await message.edit(embed=embed)
                    log_message(f"Successfully updated the embed for {phase}")
        
        log_message(
            f"Successfully outputted {successfully_posted} of {total} game updates",
            "bot",
        )

        if successfully_posted:
            with open(
                f"data/newly_finished_games.json", "w", encoding="utf-8"
            ) as output_file:
                # Reset the buffer file
                log_message(
                    "Resetting the buffer file after posting game updates", "bot"
                )
                json.dump(jsonpickle.encode({}), output_file)

    async def on_ready(self):
        await self.add_cog(NCComands(self))
        # Start schedulers (only on first run)
        if not self.jobs_scheduled:
            log_message("Scheduled post_game_updates_job", "bot")
            self.jobs_scheduled = True
            scheduler = AsyncIOScheduler()
            scheduler.add_job(
                self.post_game_updates_job,
                CronTrigger(hour="*", minute="*/5", second="0"),
            )
            scheduler.start()
