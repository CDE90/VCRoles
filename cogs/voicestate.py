import discord
from discord.ext import commands
from prisma.enums import LinkType

from utils import VCRolesClient
from utils.types import (
    ActiveGuildsData,
    LogLevel,
    MentionableRole,
    SuffixConstructor,
    VoiceStateReturnData,
)
from voicestate import Generator, Logging


class VoiceState(commands.Cog):
    def __init__(self, client: VCRolesClient):
        self.client = client
        self.generator = Generator(client)
        self.logging = Logging(client)

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ):
        if member.bot:
            return

        # Joining
        if not before.channel and after.channel:
            roles_changed, failed_roles = await self.join(member, after)

            if failed_roles:
                self.client.log(
                    LogLevel.INFO,
                    f"Failed to change roles on join: m/{member.id} c/{after.channel.id} g/{member.guild.id} r/({','.join(map(lambda x: str(x.id), failed_roles))})",
                )

            await self.logging.log_join(
                after.channel,
                member,
                roles_changed,
                failed_roles,
            )

        # Leaving
        elif before.channel and not after.channel:
            roles_changed, failed_roles = await self.leave(member, before)

            if failed_roles:
                self.client.log(
                    LogLevel.INFO,
                    f"Failed to change roles on leave: m/{member.id} c/{before.channel.id} g/{member.guild.id} r/({','.join(map(lambda x: str(x.id), failed_roles))})",
                )

            await self.logging.log_leave(
                before.channel,
                member,
                roles_changed,
                failed_roles,
            )

        # Changing
        elif before.channel and after.channel and before.channel != after.channel:

            leave_roles_changed, join_roles_changed, failed_roles = await self.change(
                member, before, after
            )

            if failed_roles:
                self.client.log(
                    LogLevel.INFO,
                    f"Failed to change roles on change: m/{member.id} c/{before.channel.id} g/{member.guild.id} r/({','.join(map(lambda x: str(x.id), failed_roles))})",
                )

            await self.logging.log_change(
                before.channel,
                after.channel,
                member,
                leave_roles_changed,
                join_roles_changed,
                failed_roles,
            )

        if (
            isinstance(before.channel, discord.StageChannel)
            and isinstance(after.channel, discord.StageChannel)
            and before.channel.id == after.channel.id
        ):
            # Become Speaker
            if before.suppress and not after.suppress:
                data = await self.client.db.get_channel_linked(
                    before.channel.id, member.guild.id, LinkType.STAGE
                )

                for role_id in data.speakerRoles:
                    role = member.guild.get_role(int(role_id))
                    if not role:
                        continue

                    try:
                        await member.add_roles(role, reason="Became Speaker")
                    except discord.errors.Forbidden:
                        pass
                    except discord.errors.HTTPException:
                        pass

            # Stop Speaker
            elif not before.suppress and after.suppress:
                data = await self.client.db.get_channel_linked(
                    before.channel.id, member.guild.id, LinkType.STAGE
                )

                for role_id in data.speakerRoles:
                    role = member.guild.get_role(int(role_id))
                    if not role:
                        continue

                    try:
                        await member.remove_roles(role, reason="Stopped Speaker")
                    except discord.errors.Forbidden:
                        pass
                    except discord.errors.HTTPException:
                        pass

    async def join(
        self,
        member: discord.Member,
        after: discord.VoiceState,
    ) -> tuple[list[VoiceStateReturnData], list[discord.Role]]:
        if not after.channel:
            # Unreachable.
            return [], []

        links = await self.client.db.get_all_linked_channel(
            member.guild.id,
            after.channel.id,
            after.channel.category.id if after.channel.category else None,
        )

        addable_roles: list[str] = []
        removeable_roles: list[str] = []

        return_data: list[VoiceStateReturnData] = []
        suffix_data = SuffixConstructor()

        for link in links:
            if str(after.channel.id) in link.excludeChannels:
                continue
            addable_roles.extend(link.linkedRoles)
            removeable_roles.extend(link.reverseLinkedRoles)
            return_data.append(
                VoiceStateReturnData(
                    "join",
                    link.type,
                    list(map(MentionableRole, link.linkedRoles)),
                    list(map(MentionableRole, link.reverseLinkedRoles)),
                )
            )
            suffix_data.add(link.type, link.suffix or "")

        # remove duplicates
        addable_roles = list(set(addable_roles))
        removeable_roles = list(set(removeable_roles))

        # if a role appears in both lists, remove both instances
        for role in addable_roles:
            if role in removeable_roles:
                addable_roles.remove(role)
                removeable_roles.remove(role)

        failed_roles: list[discord.Role] = []

        member_roles = member.roles

        for role_id in addable_roles:
            role = member.guild.get_role(int(role_id))
            if not role:
                continue

            if not role.is_assignable():
                failed_roles.append(role)
                continue

            if role not in member_roles:
                member_roles.append(role)

        for role_id in removeable_roles:
            role = member.guild.get_role(int(role_id))
            if not role:
                continue

            if not role.is_assignable():
                failed_roles.append(role)
                continue

            if role in member_roles:
                member_roles.remove(role)

        addable_suffix = f"{suffix_data.permanent_suffix + ' ' if suffix_data.permanent_suffix else ''}{suffix_data.suffix}"
        if not member.display_name.endswith(addable_suffix):
            new_user_nickname = f"{member.display_name} {addable_suffix}"
            if len(new_user_nickname) > 32:
                new_user_nickname = member.display_name
        else:
            new_user_nickname = member.display_name

        if member_roles != member.roles or new_user_nickname != member.display_name:
            # if bot has permission to change roles and nicknames
            if (
                member.guild.me.guild_permissions.manage_nicknames
                and member.guild.me.guild_permissions.manage_roles
            ):
                if (
                    member.top_role < member.guild.me.top_role
                    and member.id != member.guild.owner_id
                    and new_user_nickname != member.display_name
                    and member_roles != member.roles
                ):
                    # change nickname and roles
                    try:
                        await member.edit(
                            roles=member_roles,
                            nick=new_user_nickname,
                            reason="Joined Voice Channel",
                        )
                    except discord.HTTPException:
                        pass
                elif (
                    member.top_role < member.guild.me.top_role
                    and member.id != member.guild.owner_id
                    and new_user_nickname != member.display_name
                ):
                    # change nickname
                    try:
                        await member.edit(
                            nick=new_user_nickname, reason="Joined Voice Channel"
                        )
                    except discord.HTTPException:
                        pass
                elif member_roles != member.roles:
                    # change roles
                    try:
                        await member.edit(
                            roles=member_roles, reason="Joined Voice Channel"
                        )
                    except discord.HTTPException:
                        pass
            # if bot has permission to change roles
            elif member.guild.me.guild_permissions.manage_roles:
                # change roles
                if member.roles != member_roles:
                    try:
                        await member.edit(
                            roles=member_roles, reason="Joined Voice Channel"
                        )
                    except discord.HTTPException:
                        pass
            # if bot has permission to change nicknames
            elif member.guild.me.guild_permissions.manage_nicknames:
                # change nickname
                if (
                    member.top_role < member.guild.me.top_role
                    and member.id != member.guild.owner_id
                    and new_user_nickname != member.display_name
                ):
                    try:
                        await member.edit(
                            nick=new_user_nickname, reason="Joined Voice Channel"
                        )
                    except discord.HTTPException:
                        pass

        if member_roles != member.roles or new_user_nickname != member.display_name:
            # set active guild for voice state
            ag = self.client.active_guilds.get(member.guild.id)
            if ag is None:
                g = ActiveGuildsData()
                g.voice_active = True
                self.client.active_guilds[member.guild.id] = g
            else:
                ag.voice_active = True
                self.client.active_guilds[member.guild.id] = ag

        self.client.incr_role_counter("added", len(addable_roles))
        self.client.incr_role_counter("removed", len(removeable_roles))

        guild = await self.client.db.get_guild_data(member.guild.id)
        if guild.premium and guild.analytics:
            self.client.incr_analytics_counter(member.guild.id, "voice_channel_joins")
            self.client.incr_analytics_counter(
                member.guild.id, "roles_added", len(addable_roles)
            )
            self.client.incr_analytics_counter(
                member.guild.id, "roles_removed", len(removeable_roles)
            )

        await self.generator.join(member, after.channel)

        return return_data, list(set(failed_roles))

    async def leave(
        self,
        member: discord.Member,
        before: discord.VoiceState,
    ) -> tuple[list[VoiceStateReturnData], list[discord.Role]]:
        if not before.channel:
            # Unreachable.
            return [], []

        links = await self.client.db.get_all_linked_channel(
            member.guild.id,
            before.channel.id,
            before.channel.category.id if before.channel.category else None,
        )

        addable_roles: list[str] = []
        removeable_roles: list[str] = []

        return_data: list[VoiceStateReturnData] = []
        suffix_data = SuffixConstructor()

        for link in links:
            if str(before.channel.id) in link.excludeChannels:
                continue
            if link.type == LinkType.PERMANENT:
                continue
            addable_roles.extend(link.reverseLinkedRoles)
            removeable_roles.extend(link.linkedRoles)
            return_data.append(
                VoiceStateReturnData(
                    "leave",
                    link.type,
                    list(map(MentionableRole, link.reverseLinkedRoles)),
                    list(map(MentionableRole, link.linkedRoles)),
                )
            )
            suffix_data.add(link.type, link.suffix or "")

        # remove duplicates
        addable_roles = list(set(addable_roles))
        removeable_roles = list(set(removeable_roles))

        # if a role appears in both lists, remove both instances
        for role in addable_roles:
            if role in removeable_roles:
                addable_roles.remove(role)
                removeable_roles.remove(role)

        failed_roles: list[discord.Role] = []

        fetched_member = await before.channel.guild.fetch_member(member.id)

        member_roles = fetched_member.roles

        for role_id in addable_roles:
            role = member.guild.get_role(int(role_id))
            if not role:
                continue

            if not role.is_assignable():
                failed_roles.append(role)
                continue

            if role not in member_roles:
                member_roles.append(role)

        for role_id in removeable_roles:
            role = member.guild.get_role(int(role_id))
            if not role:
                continue

            if not role.is_assignable():
                failed_roles.append(role)
                continue

            if role in member_roles:
                member_roles.remove(role)

        new_user_nickname = fetched_member.display_name.removesuffix(suffix_data.suffix)

        if (
            member_roles != fetched_member.roles
            or new_user_nickname != fetched_member.display_name
        ):
            if (
                member.guild.me.guild_permissions.manage_nicknames
                and member.guild.me.guild_permissions.manage_roles
            ):
                if (
                    member.top_role < member.guild.me.top_role
                    and member.id != member.guild.owner_id
                    and new_user_nickname != fetched_member.display_name
                    and member_roles != fetched_member.roles
                ):
                    try:
                        await member.edit(
                            roles=member_roles,
                            nick=new_user_nickname,
                            reason="Left Voice Channel",
                        )
                    except discord.HTTPException:
                        pass
                elif (
                    member.top_role < member.guild.me.top_role
                    and member.id != member.guild.owner_id
                    and new_user_nickname != fetched_member.display_name
                ):
                    try:
                        await member.edit(
                            nick=new_user_nickname, reason="Left Voice Channel"
                        )
                    except discord.HTTPException:
                        pass
                elif member_roles != fetched_member.roles:
                    try:
                        await member.edit(
                            roles=member_roles, reason="Left Voice Channel"
                        )
                    except discord.HTTPException:
                        pass
            elif member.guild.me.guild_permissions.manage_roles:
                if member_roles != fetched_member.roles:
                    try:
                        await member.edit(
                            roles=member_roles, reason="Left Voice Channel"
                        )
                    except discord.HTTPException:
                        pass
            elif (
                member.guild.me.guild_permissions.manage_nicknames
                and member.top_role < member.guild.me.top_role
                and member.id != member.guild.owner_id
                and new_user_nickname != fetched_member.display_name
            ):
                try:
                    await member.edit(
                        nick=new_user_nickname, reason="Left Voice Channel"
                    )
                except discord.HTTPException:
                    pass

        if (
            member_roles != fetched_member.roles
            or new_user_nickname != fetched_member.display_name
        ):
            ag = self.client.active_guilds.get(member.guild.id)
            if ag is None:
                g = ActiveGuildsData()
                g.voice_active = True
                self.client.active_guilds[member.guild.id] = g
            else:
                ag.voice_active = True
                self.client.active_guilds[member.guild.id] = ag

        self.client.incr_role_counter("added", len(addable_roles))
        self.client.incr_role_counter("removed", len(removeable_roles))

        guild = await self.client.db.get_guild_data(member.guild.id)
        if guild.premium and guild.analytics:
            self.client.incr_analytics_counter(member.guild.id, "voice_channel_leaves")
            self.client.incr_analytics_counter(
                member.guild.id, "roles_added", len(addable_roles)
            )
            self.client.incr_analytics_counter(
                member.guild.id, "roles_removed", len(removeable_roles)
            )

        await self.generator.leave(member, before.channel)

        return return_data, list(set(failed_roles))

    async def change(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ) -> tuple[
        list[VoiceStateReturnData], list[VoiceStateReturnData], list[discord.Role]
    ]:
        if not before.channel or not after.channel:
            # Unreachable.
            return [], [], []

        before_links = await self.client.db.get_all_linked_channel(
            member.guild.id,
            before.channel.id,
            before.channel.category.id if before.channel.category else None,
        )

        after_links = await self.client.db.get_all_linked_channel(
            member.guild.id,
            after.channel.id,
            after.channel.category.id if after.channel.category else None,
        )

        addable_roles: list[str] = []
        removeable_roles: list[str] = []

        leave_return_data: list[VoiceStateReturnData] = []
        join_return_data: list[VoiceStateReturnData] = []

        leave_suffix_data = SuffixConstructor()
        join_suffix_data = SuffixConstructor()

        for link in before_links:
            if str(before.channel.id) in link.excludeChannels:
                continue
            if link.type == LinkType.PERMANENT:
                continue
            addable_roles.extend(link.reverseLinkedRoles)
            removeable_roles.extend(link.linkedRoles)
            leave_return_data.append(
                VoiceStateReturnData(
                    "leave",
                    link.type,
                    list(map(MentionableRole, link.reverseLinkedRoles)),
                    list(map(MentionableRole, link.linkedRoles)),
                )
            )
            leave_suffix_data.add(link.type, link.suffix or "")

        for link in after_links:
            if str(after.channel.id) in link.excludeChannels:
                continue
            addable_roles.extend(link.linkedRoles)
            removeable_roles.extend(link.reverseLinkedRoles)
            join_return_data.append(
                VoiceStateReturnData(
                    "join",
                    link.type,
                    list(map(MentionableRole, link.linkedRoles)),
                    list(map(MentionableRole, link.reverseLinkedRoles)),
                )
            )
            join_suffix_data.add(link.type, link.suffix or "")

        # remove duplicates
        addable_roles = list(set(addable_roles))
        removeable_roles = list(set(removeable_roles))

        # if a role appears in both lists, remove both instances
        for role in addable_roles:
            if role in removeable_roles:
                addable_roles.remove(role)
                removeable_roles.remove(role)

        failed_roles: list[discord.Role] = []

        fetched_member = await before.channel.guild.fetch_member(member.id)

        member_roles = fetched_member.roles

        for role_id in addable_roles:
            role = member.guild.get_role(int(role_id))
            if not role:
                continue

            if not role.is_assignable():
                failed_roles.append(role)
                continue

            if role not in member_roles:
                member_roles.append(role)

        for role_id in removeable_roles:
            role = member.guild.get_role(int(role_id))
            if not role:
                continue

            if not role.is_assignable():
                failed_roles.append(role)
                continue

            if role in member_roles:
                member_roles.remove(role)

        removed_leave_suffix = fetched_member.display_name.removesuffix(
            leave_suffix_data.suffix
        )
        addable_suffix = f" {join_suffix_data.permanent_suffix + ' ' if join_suffix_data.permanent_suffix else ''}{join_suffix_data.suffix}"
        if len(removed_leave_suffix + addable_suffix) > 32:
            new_user_nickname = removed_leave_suffix
        else:
            if not removed_leave_suffix.endswith(addable_suffix):
                new_user_nickname = removed_leave_suffix + addable_suffix
            else:
                new_user_nickname = removed_leave_suffix

        if (
            member_roles != fetched_member.roles
            or new_user_nickname != fetched_member.display_name
        ):
            if (
                member.guild.me.guild_permissions.manage_nicknames
                and member.guild.me.guild_permissions.manage_roles
            ):
                if (
                    fetched_member.top_role < member.guild.me.top_role
                    and member.id != member.guild.owner_id
                    and new_user_nickname != fetched_member.display_name
                    and member_roles != fetched_member.roles
                ):
                    try:
                        await member.edit(
                            roles=member_roles,
                            nick=new_user_nickname,
                            reason="Changed Voice Channel",
                        )
                    except discord.HTTPException:
                        pass
                elif (
                    fetched_member.top_role < member.guild.me.top_role
                    and member.id != member.guild.owner_id
                    and new_user_nickname != fetched_member.display_name
                ):
                    try:
                        await member.edit(
                            nick=new_user_nickname,
                            reason="Changed Voice Channel",
                        )
                    except discord.HTTPException:
                        pass
                elif member_roles != fetched_member.roles:
                    try:
                        await member.edit(
                            roles=member_roles,
                            reason="Changed Voice Channel",
                        )
                    except discord.HTTPException:
                        pass
            elif member.guild.me.guild_permissions.manage_roles:
                if member_roles != fetched_member.roles:
                    try:
                        await member.edit(
                            roles=member_roles,
                            reason="Changed Voice Channel",
                        )
                    except discord.HTTPException:
                        pass
            elif (
                member.guild.me.guild_permissions.manage_nicknames
                and fetched_member.top_role < member.guild.me.top_role
                and member.id != member.guild.owner_id
                and new_user_nickname != fetched_member.display_name
            ):
                try:
                    await member.edit(
                        nick=new_user_nickname,
                        reason="Changed Voice Channel",
                    )
                except discord.HTTPException:
                    pass

        if (
            member_roles != fetched_member.roles
            or new_user_nickname != fetched_member.display_name
        ):
            ag = self.client.active_guilds.get(member.guild.id)
            if ag is None:
                g = ActiveGuildsData()
                g.voice_active = True
                self.client.active_guilds[member.guild.id] = g
            else:
                ag.voice_active = True
                self.client.active_guilds[member.guild.id] = ag

        self.client.incr_role_counter("added", len(addable_roles))
        self.client.incr_role_counter("removed", len(removeable_roles))

        guild = await self.client.db.get_guild_data(member.guild.id)
        if guild.premium and guild.analytics:
            self.client.incr_analytics_counter(member.guild.id, "voice_channel_changes")
            self.client.incr_analytics_counter(
                member.guild.id, "roles_added", len(addable_roles)
            )
            self.client.incr_analytics_counter(
                member.guild.id, "roles_removed", len(removeable_roles)
            )

        await self.generator.leave(member, before.channel)
        await self.generator.join(member, after.channel)

        return leave_return_data, join_return_data, list(set(failed_roles))


async def setup(client: VCRolesClient):
    await client.add_cog(VoiceState(client))
