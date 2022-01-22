import discord
from discord.ext import commands
from discord.commands import Option
from bot import MyClient


class Unlink(commands.Cog):
    def __init__(self, client: MyClient):
        self.client = client

    @commands.slash_command(
        description="Use to remove any channel/category from all links (Using ID)"
    )
    @commands.has_permissions(administrator=True)
    async def forceunlink(
        self,
        ctx: discord.ApplicationContext,
        channel_id: Option(str, "Enter the channel ID"),
    ):

        data = self.client.redis.get_linked("voice", ctx.guild.id)
        if str(channel_id) in data:
            del data[str(channel_id)]
            self.client.redis.update_linked("voice", ctx.guild.id, data)

        data = self.client.redis.get_linked("permanent", ctx.guild.id)
        if str(channel_id) in data:
            del data[str(channel_id)]
            self.client.redis.update_linked("permanent", ctx.guild.id, data)

        data = self.client.redis.get_linked("all", ctx.guild.id)
        if str(channel_id) in data["except"]:
            data["except"].remove(str(channel_id))
            self.client.redis.update_linked("all", ctx.guild.id, data)

        data = self.client.redis.get_linked("stage", ctx.guild.id)
        if str(channel_id) in data:
            del data[str(channel_id)]
            self.client.redis.update_linked("stage", ctx.guild.id, data)

        data = self.client.redis.get_linked("category", ctx.guild.id)
        if str(channel_id) in data:
            del data[str(channel_id)]
            self.client.redis.update_linked("category", ctx.guild.id, data)

        await ctx.respond(f"Any found links to {channel_id} have been removed.")


def setup(client: MyClient):
    client.add_cog(Unlink(client))