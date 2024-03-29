from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from utils.checks import check_any, command_available, is_owner
from utils.client import VCRolesClient
from utils.types import LogLevel


class Logging(commands.Cog):
    def __init__(self, client: VCRolesClient):
        self.client = client

    @app_commands.command()
    @app_commands.describe(
        enabled="Enter 'true' to enable or 'false' to disable",
        channel="Logging channel:",
    )
    @check_any(command_available, is_owner)
    @app_commands.checks.has_permissions(administrator=True)
    async def logging(
        self,
        interaction: discord.Interaction,
        enabled: bool,
        channel: Optional[discord.TextChannel] = None,
    ):
        """Used to enable or disable logging in a channel."""
        if (
            not interaction.guild
            or not interaction.channel
            or not isinstance(interaction.channel, discord.TextChannel)
        ):
            return await interaction.response.send_message(
                "You must be in a server to use this command."
            )

        if enabled and not channel:
            channel = interaction.channel
        if enabled and channel:
            await self.client.db.update_guild_data(
                interaction.guild.id, logging=str(channel.id)
            )

            await interaction.response.send_message(
                f"Successfully enabled logging in {channel.mention}"
            )
        elif not enabled:
            await self.client.db.update_guild_data(interaction.guild.id, logging="None")

            await interaction.response.send_message("Successfully disabled logging")

        self.client.log(
            LogLevel.DEBUG,
            f"Logging {'enabled' if enabled else 'disabled'} g/{interaction.guild.id}",
        )


async def setup(client: VCRolesClient):
    await client.add_cog(Logging(client))
