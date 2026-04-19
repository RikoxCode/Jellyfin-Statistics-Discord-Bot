from pathlib import Path
import os
import sys

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv(*args, **kwargs):
        return False

SRC_DIR = Path(__file__).resolve().parent
ROOT_DIR = SRC_DIR.parent
DISCORD_DIR = SRC_DIR / "discord"
ENV_PATH = ROOT_DIR / ".env"

for module_path in (SRC_DIR, DISCORD_DIR):
    if str(module_path) not in sys.path:
        sys.path.insert(0, str(module_path))

from jellyfin.jellyfin import JellyfinClient, JellyfinService
from jellyfin.playback_reporting import PlaybackReporting
from utils.config_manager import AppConfigManager, FunctionConfigManager, CHANNELS_CONFIG_PATH
from bot_client import JellyfinStatisticsBot
from channel_manager import DiscordChannelManager
from stats_provider import JellyfinStatsProvider


def load_environment():
    load_dotenv(dotenv_path=ENV_PATH)


def create_jellyfin_client():
    load_environment()

    base_url = os.getenv("JELLYFIN_SERVER_URL")
    api_key = os.getenv("JELLYFIN_API_KEY")

    if not base_url or not api_key:
        raise ValueError(
            "Missing Jellyfin configuration. Please set JELLYFIN_SERVER_URL and JELLYFIN_API_KEY in the .env file."
        )

    return JellyfinClient(base_url=base_url, api_key=api_key, timeout=10)


def create_discord_bot():
    app_config = AppConfigManager()
    function_config = FunctionConfigManager()

    jellyfin_client = create_jellyfin_client()
    jellyfin_service = JellyfinService(jellyfin_client)
    playback_reporting = PlaybackReporting(jellyfin_client)

    stats_provider = JellyfinStatsProvider(jellyfin_service, playback_reporting, function_config)
    channel_manager = DiscordChannelManager(app_config, stats_provider, CHANNELS_CONFIG_PATH)

    return JellyfinStatisticsBot(app_config, channel_manager)


def main():
    load_environment()

    discord_token = os.getenv("DISCORD_TOKEN")
    if not discord_token:
        raise ValueError("Missing Discord configuration. Please set DISCORD_TOKEN in the .env file.")

    bot = create_discord_bot()
    bot.run(discord_token)


if __name__ == "__main__":
    main()