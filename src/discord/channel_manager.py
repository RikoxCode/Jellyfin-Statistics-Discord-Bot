import asyncio
import json
from pathlib import Path

import discord


class DiscordChannelManager:
    def __init__(self, app_config, stats_provider, storage_path=None):
        self.app_config = app_config
        self.stats_provider = stats_provider
        default_storage = Path(__file__).resolve().parent.parent / "config" / "channels.json"
        self.storage_path = Path(storage_path) if storage_path else default_storage
        self._storage = self._load_storage()

    def get_configured_channel_specs(self):
        specs = []
        for stat in self.app_config.get("channel.showed_stats", []):
            function_key = stat.get("value")
            if not function_key or not self.stats_provider.is_enabled(function_key):
                continue

            value = self.stats_provider.get_stat_value(function_key)
            title = stat.get("title", stat.get("key", function_key))
            icon = stat.get("icon", "")

            specs.append(
                {
                    "key": stat.get("key", function_key),
                    "title": title,
                    "icon": icon,
                    "name": self._build_channel_name(icon, title, value),
                    "match_text": f"{icon} {title}".strip().lower(),
                }
            )
        return specs

    async def sync_guild(self, guild):
        category = await self._ensure_category(guild)
        specs = await asyncio.to_thread(self.get_configured_channel_specs)

        for position, spec in enumerate(specs):
            channel = await self._ensure_channel(guild, category, spec, position)
            if channel is not None:
                self._remember_channel(guild.id, spec["key"], channel.id)

        self._save_storage()

    async def _ensure_category(self, guild):
        use_category = bool(self.app_config.get("category.use", False))
        if not use_category:
            return None

        category_name = self.app_config.get("category.name", "Statistics")
        overwrites = self._get_permission_overwrites(guild)
        category = discord.utils.get(guild.categories, name=category_name)
        if category is None:
            category = await guild.create_category(category_name, overwrites=overwrites)
        elif overwrites:
            await category.edit(overwrites=overwrites)
        return category

    async def _ensure_channel(self, guild, category, spec, position):
        existing_channel = self._find_existing_channel(guild, category, spec)
        overwrites = self._get_permission_overwrites(guild)
        if existing_channel is not None:
            changes = {}
            if existing_channel.name != spec["name"]:
                changes["name"] = spec["name"]
            if category is not None and getattr(existing_channel, "category_id", None) != category.id:
                changes["category"] = category
            if overwrites:
                changes["overwrites"] = overwrites
            if changes:
                await existing_channel.edit(**changes)
            return existing_channel

        if self._get_channel_type() == "text":
            return await guild.create_text_channel(spec["name"], category=category, position=position, overwrites=overwrites)

        return await guild.create_voice_channel(spec["name"], category=category, position=position, overwrites=overwrites)

    def _find_existing_channel(self, guild, category, spec):
        persistent_channel_id = self._get_persisted_channel_id(guild.id, spec["key"])
        if persistent_channel_id is not None:
            channel = guild.get_channel(persistent_channel_id)
            if channel is not None:
                return channel

        for channel in guild.channels:
            if self._get_channel_type() == "voice" and not isinstance(channel, discord.VoiceChannel):
                continue
            if self._get_channel_type() == "text" and not isinstance(channel, discord.TextChannel):
                continue

            if category is not None and getattr(channel, "category_id", None) != category.id:
                continue

            if spec["match_text"] and spec["match_text"] in channel.name.lower():
                return channel
        return None

    def _load_storage(self):
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.storage_path.exists():
            return {"guilds": {}}

        try:
            with open(self.storage_path, "r", encoding="utf-8") as file:
                data = json.load(file)
                if isinstance(data, dict):
                    data.setdefault("guilds", {})
                    return data
        except (json.JSONDecodeError, OSError):
            pass

        return {"guilds": {}}

    def _save_storage(self):
        with open(self.storage_path, "w", encoding="utf-8") as file:
            json.dump(self._storage, file, indent=2, ensure_ascii=False)

    def _remember_channel(self, guild_id, stat_key, channel_id):
        guild_key = str(guild_id)
        self._storage.setdefault("guilds", {})
        self._storage["guilds"].setdefault(guild_key, {})
        self._storage["guilds"][guild_key][stat_key] = channel_id

    def _get_persisted_channel_id(self, guild_id, stat_key):
        return self._storage.get("guilds", {}).get(str(guild_id), {}).get(stat_key)

    def _get_channel_type(self):
        channel_type = str(self.app_config.get("channel.type", "voice")).lower()
        return "text" if channel_type == "text" else "voice"

    def _get_permission_overwrites(self, guild):
        if not bool(self.app_config.get("channel.private", False)):
            return None

        default_deny = discord.PermissionOverwrite(
            view_channel=True,
            send_messages=False,
            read_message_history=True,
            connect=False,
            speak=False,
        )
        bot_allow = discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True,
            connect=True,
            speak=True,
            manage_channels=True,
        )
        return {
            guild.default_role: default_deny,
            guild.me: bot_allow,
        }

    def _build_channel_name(self, icon, title, value):
        template = self.app_config.get("channel.name_template", "{icon} {title}: {value}")
        formatted_value = self._format_value(value)
        name = template.format(icon=icon, title=title, value=formatted_value).strip()
        return " ".join(name.split())[:100]

    def _format_value(self, value):
        if isinstance(value, float):
            return f"{value:.2f}h"
        if isinstance(value, list):
            text = ", ".join(str(item) for item in value if item)
            return text or "0"
        if value is None:
            return "0"
        return str(value)
