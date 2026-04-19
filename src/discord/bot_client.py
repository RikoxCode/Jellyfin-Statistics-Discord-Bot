import discord
from discord.ext import commands, tasks


class JellyfinStatisticsBot(commands.Bot):
    def __init__(self, app_config, channel_manager):
        intents = discord.Intents.default()
        intents.guilds = True
        intents.message_content = True

        command_prefix = app_config.get("bot.command_prefix", "!")
        super().__init__(command_prefix=command_prefix, intents=intents)

        self.app_config = app_config
        self.channel_manager = channel_manager
        self.update_interval_seconds = max(int(app_config.get("update_interval", 60000)) / 1000, 30)

    async def setup_hook(self):
        if self.app_config.get("bot.refresh_enabled", True) and self.get_command("refresh") is None:
            @commands.command(name="refresh")
            @commands.has_permissions(manage_channels=True)
            async def refresh_command(ctx):
                await ctx.send("Refreshing statistics channels...")
                await self.sync_all_guilds()
                await ctx.send("Statistics channels updated.")

            self.add_command(refresh_command)

        self.refresh_channels_loop.change_interval(seconds=self.update_interval_seconds)
        if not self.refresh_channels_loop.is_running():
            self.refresh_channels_loop.start()

    async def on_ready(self):
        if self.user is not None:
            print(f"Logged in as {self.user} ({self.user.id})")
        await self.sync_all_guilds()

    async def sync_all_guilds(self):
        for guild in self.guilds:
            try:
                await self.channel_manager.sync_guild(guild)
                print(f"Synchronized statistic channels for guild: {guild.name}")
            except Exception as exc:
                print(f"Failed to synchronize guild '{guild.name}': {exc}")

    @tasks.loop(seconds=60)
    async def refresh_channels_loop(self):
        if self.is_ready():
            await self.sync_all_guilds()
