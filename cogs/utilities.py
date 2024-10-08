from string import Template
from typing import Union

import discord
from discord import Interaction, app_commands
from discord.ext import commands

from utils.client import VCRolesClient
from views.url import Combination, Discord, Invite, TopGG, Website


class Utils(commands.Cog):
    def __init__(self, client: VCRolesClient):
        self.client = client

    @app_commands.command()
    @app_commands.describe(
        channel="Channel to mention:",
        message="Message to send using $name and $mention variables:",
    )
    async def mention(
        self,
        interaction: Interaction,
        channel: Union[discord.VoiceChannel, discord.StageChannel],
        message: str = "$mention",
    ):
        """Use to mention a channel in chat"""
        await interaction.response.send_message(
            Template(message).substitute(
                name=channel.name, mention=channel.mention, channel=channel
            )
        )

    @app_commands.command(name="discord")
    async def support_server(self, interaction: discord.Interaction):
        """Use to get an invite to the support server"""
        await interaction.response.send_message(
            content="To join our support server, click the link below", view=Discord()
        )

    @app_commands.command()
    async def invite(self, interaction: Interaction):
        """Use to get an invite for the bot"""
        await interaction.response.send_message(
            content="To invite the bot, use the link below",
            view=Invite(),
        )

    @app_commands.command()
    async def topgg(self, interaction: Interaction):
        """Use to get a link to the bot's Top.gg page"""
        await interaction.response.send_message(
            content="To visit the bot's Top.gg, click the link below", view=TopGG()
        )

    @app_commands.command()
    async def about(self, interaction: Interaction):
        """Use to get info about the bot"""
        embed = discord.Embed(title="About:", colour=discord.Colour.blue())

        total_commands = 0
        total_roles_changed = 0
        counters = await self.client.ar.hgetall("counters")
        for key, value in counters.items():
            if key not in ["roles_added", "roles_removed"]:
                total_commands += int(value)
            elif key in ["roles_added", "roles_removed"]:
                total_roles_changed += int(value)

        total_members = 0
        voice = 0
        guilds = 0
        for guild in self.client.guilds:
            guilds += 1
            if guild.unavailable:
                continue

            total_members += guild.member_count if guild.member_count else 0
            for channel in guild.channels:
                if isinstance(channel, discord.VoiceChannel):
                    voice += 1

        embed.add_field(
            name="Server Count",
            value=f"{self.client.user.name if self.client.user else 'VC Roles'} is in {guilds:,} servers",
            inline=False,
        )
        embed.add_field(
            name="Statistics",
            value=f"{total_members:,} total members\n{voice:,} voice channels\n{total_commands:,} commands used\n{total_roles_changed:,} roles changed",
        )
        embed.add_field(
            name="Shard Info",
            value=f"This is shard {interaction.guild.shard_id if interaction.guild else 0}\nThere are {len(self.client.shards)} shards",
        )
        embed.add_field(
            name="Authors",
            value="Currently @ethancoward [CDE90](https://github.com/CDE90).\nPreviously @ethancoward and @samhartland [DrWackyBob](https://github.com/DrWackyBob)",
            inline=False,
        )
        embed.set_author(
            name=f"{self.client.user}",
            icon_url=self.client.user.avatar.url
            if self.client.user and self.client.user.avatar
            else None,
        )

        await interaction.response.send_message(embed=embed, view=Combination())

    @app_commands.command()
    async def help(self, interaction: Interaction):
        """Use to get help about the bot"""
        embed = discord.Embed(
            title="VC Roles Help",
            description="We have moved our help page to https://www.vcroles.com where you can find a list of the bot's commands, how to use them, a basic setup guide and more!",
            colour=discord.Colour.light_grey(),
        )
        await interaction.response.send_message(embed=embed, view=Website())

    @app_commands.command()
    @app_commands.checks.has_permissions(administrator=True)
    async def update_channel(
        self, interaction: Interaction, channel: discord.TextChannel
    ):
        """Use to set the channel to send updates to"""
        if not interaction.guild:
            return await interaction.response.send_message(
                content="You can only use this command in a server"
            )

        # create a webhook in the channel and save the webhook url in redis for later use
        webhook = await channel.create_webhook(name="VC Roles")
        await self.client.ar.hset("webhooks", str(interaction.guild.id), webhook.url)

        await interaction.response.send_message(
            content=f"Successfully set the update channel to {channel.mention}"
        )

        await self.client.send_welcome(interaction.guild.id)


async def setup(client: VCRolesClient):
    await client.add_cog(Utils(client))
