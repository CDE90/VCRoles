import discord
from discord import app_commands
from discord.ext import commands
from prisma.enums import LinkType

from utils.checks import check_any, command_available, is_owner
from utils.client import VCRolesClient
from utils.linking import LinkingUtils
from utils.types import LinkableChannel, LogLevel, RoleCategory


class PermLink(commands.Cog):
    def __init__(self, client: VCRolesClient):
        self.client = client
        self.linking = LinkingUtils(client)

    perm_commands = app_commands.Group(
        name="permanent", description="Rules to apply to permanent channels"
    )
    suffix_commands = app_commands.Group(
        name="suffix",
        description="Suffix to add to the end of usernames",
        parent=perm_commands,
    )
    reverse_commands = app_commands.Group(
        name="reverse", description="Reverse roles", parent=perm_commands
    )

    @perm_commands.command()
    @app_commands.describe(
        channel="Select a channel to link", role="Select a role to link"
    )
    @check_any(command_available, is_owner)
    @app_commands.checks.has_permissions(administrator=True)
    async def link(
        self,
        interaction: discord.Interaction,
        channel: LinkableChannel,
        role: discord.Role,
    ):
        """Use to link a channel and a role (after leaving channel, user will keep role)"""

        data = await self.linking.link(
            interaction, channel, role, LinkType.PERMANENT, RoleCategory.REGULAR
        )

        await interaction.response.send_message(data.message)

        self.client.log(
            LogLevel.DEBUG,
            f"Permanent linked c/{channel.id} g/{interaction.guild_id} r/{role.id}",
        )

    @perm_commands.command()
    @app_commands.describe(
        channel="Select a channel to unlink", role="Select a role to unlink"
    )
    @check_any(command_available, is_owner)
    @app_commands.checks.has_permissions(administrator=True)
    async def unlink(
        self,
        interaction: discord.Interaction,
        channel: LinkableChannel,
        role: discord.Role,
    ):
        """Use to unlink a "permanent" channel from a role"""

        data = await self.linking.unlink(
            interaction, channel, role, LinkType.PERMANENT, RoleCategory.REGULAR
        )

        await interaction.response.send_message(data.message)

        self.client.log(
            LogLevel.DEBUG,
            f"Permanent unlinked c/{channel.id} g/{interaction.guild_id} r/{role.id}",
        )

    @suffix_commands.command()
    @app_commands.describe(
        channel="Select a channel to set a suffix for",
        suffix="Suffix to add to the end of usernames",
    )
    @check_any(command_available, is_owner)
    @app_commands.checks.has_permissions(administrator=True)
    async def add(
        self,
        interaction: discord.Interaction,
        channel: LinkableChannel,
        suffix: str,
    ):
        """Use to set a suffix to add to the end of usernames"""

        data = await self.linking.suffix_add(
            interaction, channel, suffix, LinkType.PERMANENT
        )

        await interaction.response.send_message(data.message)

        self.client.log(
            LogLevel.DEBUG,
            f"Permanent suffix added c/{channel.id} g/{interaction.guild_id} s/{suffix}",
        )

    @suffix_commands.command()
    @app_commands.describe(channel="Select a channel to remove a suffix rule from")
    @check_any(command_available, is_owner)
    @app_commands.checks.has_permissions(administrator=True)
    async def remove(
        self,
        interaction: discord.Interaction,
        channel: LinkableChannel,
    ):
        """Use to remove a suffix rule from a channel"""

        data = await self.linking.suffix_remove(
            interaction, channel, LinkType.PERMANENT
        )

        await interaction.response.send_message(data.message)

        self.client.log(
            LogLevel.DEBUG,
            f"Permanent suffix removed c/{channel.id} g/{interaction.guild_id}",
        )

    @reverse_commands.command(
        name="link",
    )
    @app_commands.describe(
        channel="Select a channel to link", role="Select a role to link"
    )
    @check_any(command_available, is_owner)
    @app_commands.checks.has_permissions(administrator=True)
    async def reverse_link(
        self,
        interaction: discord.Interaction,
        channel: LinkableChannel,
        role: discord.Role,
    ):
        """Use to reverse link a channel and a role"""

        data = await self.linking.link(
            interaction, channel, role, LinkType.PERMANENT, RoleCategory.REVERSE
        )

        await interaction.response.send_message(data.message)

        self.client.log(
            LogLevel.DEBUG,
            f"Permanent reverse linked c/{channel.id} g/{interaction.guild_id} r/{role.id}",
        )

    @reverse_commands.command(
        name="unlink",
    )
    @app_commands.describe(
        channel="Select a channel to unlink", role="Select a role to unlink"
    )
    @check_any(command_available, is_owner)
    @app_commands.checks.has_permissions(administrator=True)
    async def reverse_unlink(
        self,
        interaction: discord.Interaction,
        channel: LinkableChannel,
        role: discord.Role,
    ):
        """Use to unlink a reverse role"""

        data = await self.linking.unlink(
            interaction, channel, role, LinkType.PERMANENT, RoleCategory.REVERSE
        )

        await interaction.response.send_message(data.message)

        self.client.log(
            LogLevel.DEBUG,
            f"Permanent reverse unlinked c/{channel.id} g/{interaction.guild_id} r/{role.id}",
        )


async def setup(client: VCRolesClient):
    await client.add_cog(PermLink(client))
