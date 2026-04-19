import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC_DIR = ROOT / "src"
DISCORD_DIR = SRC_DIR / "discord"

for module_path in (SRC_DIR, DISCORD_DIR):
    if str(module_path) not in sys.path:
        sys.path.insert(0, str(module_path))

from channel_manager import DiscordChannelManager
from jellyfin.jellyfin import JellyfinClient, JellyfinService
from jellyfin.playback_reporting import PlaybackReporting
from main import create_discord_bot, create_jellyfin_client
from stats_provider import JellyfinStatsProvider
from utils.config_manager import AppConfigManager, FunctionConfigManager


class FakeClient:
    def __init__(self, responses=None):
        self.responses = responses or {}
        self.calls = []

    def request(self, endpoint, method="GET", body=None, params=None):
        self.calls.append(
            {
                "endpoint": endpoint,
                "method": method,
                "body": body,
                "params": params,
            }
        )
        return self.responses.get(endpoint, {})

    def get_headers(self):
        return {"Authorization": "MediaBrowser Token=fake"}


class DummyConfig:
    def __init__(self, data):
        self.data = data

    def get(self, key, default=None):
        current = self.data
        for part in str(key).split("."):
            if not isinstance(current, dict):
                return default
            current = current.get(part, default)
        return current


class FakeStatsProvider:
    def __init__(self):
        self.enabled = {"get_user_count", "get_movie_count"}
        self.values = {"get_user_count": 5, "get_movie_count": 12}

    def is_enabled(self, function_key):
        return function_key in self.enabled

    def get_stat_value(self, function_key):
        return self.values.get(function_key, "n/a")


class ConfigManagerTests(unittest.TestCase):
    def test_app_config_loads_existing_values(self):
        config = AppConfigManager()

        self.assertEqual(config.get("update_interval"), 60000)
        self.assertEqual(config.get("channel.type"), "voice")
        self.assertTrue(isinstance(config.get("channel.showed_stats"), list))
        self.assertEqual(config.get("bot.command_prefix"), "!")

    def test_category_alias_works_with_existing_spelling(self):
        config = AppConfigManager()

        self.assertFalse(config.get("category.use"))
        self.assertEqual(config.get("category.name"), "📊 Stats")

    def test_function_config_loads(self):
        config = FunctionConfigManager()
        functions = config.get("functions")

        self.assertTrue(isinstance(functions, list))
        self.assertGreater(len(functions), 0)
        self.assertIn("get_user_count", [item["key"] for item in functions])

    def test_showed_stats_reference_existing_functions(self):
        app_config = AppConfigManager()
        function_config = FunctionConfigManager()

        shown = app_config.get("channel.showed_stats", [])
        available = {
            item["key"]
            for item in function_config.get("functions", [])
            if item.get("enabled")
        }

        missing = [item["value"] for item in shown if item.get("value") not in available]
        self.assertEqual(missing, [], f"Missing enabled functions for showed_stats: {missing}")


class MainTests(unittest.TestCase):
    def test_create_jellyfin_client_uses_expected_env_vars(self):
        original_server_url = os.environ.get("JELLYFIN_SERVER_URL")
        original_api_key = os.environ.get("JELLYFIN_API_KEY")

        try:
            os.environ["JELLYFIN_SERVER_URL"] = "http://example.com"
            os.environ["JELLYFIN_API_KEY"] = "secret-token"

            client = create_jellyfin_client()

            self.assertEqual(client.base_url, "http://example.com")
            self.assertEqual(client.api_key, "secret-token")
        finally:
            if original_server_url is None:
                os.environ.pop("JELLYFIN_SERVER_URL", None)
            else:
                os.environ["JELLYFIN_SERVER_URL"] = original_server_url

            if original_api_key is None:
                os.environ.pop("JELLYFIN_API_KEY", None)
            else:
                os.environ["JELLYFIN_API_KEY"] = original_api_key

    def test_create_discord_bot_builds_instance(self):
        bot = create_discord_bot()
        self.assertEqual(bot.command_prefix, "!")


class JellyfinClientTests(unittest.TestCase):
    def test_headers_contain_required_authentication(self):
        client = JellyfinClient("http://localhost:8096", "secret-token")
        headers = client.get_headers()

        self.assertEqual(headers["Accept"], "application/json")
        self.assertEqual(headers["Content-Type"], "application/json")
        self.assertEqual(headers["X-Emby-Token"], "secret-token")
        self.assertIn("MediaBrowser Token=secret-token", headers["Authorization"])

    def test_url_and_timeout_are_built_correctly(self):
        client = JellyfinClient("http://localhost:8096/", "secret-token", timeout=15)

        self.assertEqual(client.get_url("/Users"), "http://localhost:8096/Users")
        self.assertEqual(client.get_request_timeout(), 15)


class JellyfinServiceTests(unittest.TestCase):
    def test_service_uses_expected_endpoints_and_params(self):
        fake = FakeClient(
            responses={
                "/Users": [{"Name": "Alice"}],
                "/Sessions": [{"Id": "1"}],
                "/Items": {"Items": []},
            }
        )
        service = JellyfinService(fake)

        self.assertEqual(service.get_all_users(), [{"Name": "Alice"}])
        self.assertEqual(service.get_active_sessions(), [{"Id": "1"}])
        self.assertEqual(service.get_all_items(), [])
        self.assertEqual(service.get_all_movies(), [])
        self.assertEqual(service.get_all_tv_shows(), [])
        self.assertEqual(service.get_all_episodes(), [])

        self.assertEqual(
            [call["endpoint"] for call in fake.calls],
            ["/Users", "/Sessions", "/Items", "/Items", "/Items", "/Items"],
        )


class PlaybackReportingTests(unittest.TestCase):
    def test_movie_watch_time_returns_data(self):
        fake = FakeClient(
            responses={
                "/user_usage_stats/submit_custom_query": {
                    "results": [["Movie", 12.5]]
                }
            }
        )
        reporting = PlaybackReporting(fake)

        result = reporting.get_movie_watch_time()

        self.assertEqual(result, 12.5)
        self.assertEqual(fake.calls[0]["endpoint"], "/user_usage_stats/submit_custom_query")
        self.assertEqual(fake.calls[0]["method"], "POST")
        self.assertIn("PlaybackActivity", fake.calls[0]["body"]["CustomQueryString"])

    def test_movie_watch_time_returns_zero_without_data(self):
        fake = FakeClient(responses={"/user_usage_stats/submit_custom_query": {}})
        reporting = PlaybackReporting(fake)

        self.assertEqual(reporting.get_movie_watch_time(), 0)


class DiscordBotConfigTests(unittest.TestCase):
    def test_stats_provider_resolves_enabled_functions(self):
        service = type(
            "FakeService",
            (),
            {
                "get_all_users": lambda self: [1, 2],
                "get_active_sessions": lambda self: [1],
                "get_all_movies": lambda self: [1, 2, 3],
                "get_all_tv_shows": lambda self: [1, 2, 3, 4],
                "get_all_episodes": lambda self: [1, 2, 3, 4, 5],
            },
        )()
        reporting = type(
            "FakeReporting",
            (),
            {
                "get_item_play_count": lambda self, item_type: 7,
                "get_top_items": lambda self, item_type: ["A", "B"],
                "get_total_watch_time": lambda self: 10.5,
            },
        )()
        function_config = DummyConfig(
            {
                "functions": [
                    {"key": "get_user_count", "enabled": True},
                    {"key": "get_movie_count", "enabled": True},
                ]
            }
        )

        provider = JellyfinStatsProvider(service, reporting, function_config)

        self.assertEqual(provider.get_stat_value("get_user_count"), 2)
        self.assertEqual(provider.get_stat_value("get_movie_count"), 3)
        self.assertEqual(provider.get_stat_value("get_series_count"), "disabled")

    def test_channel_manager_uses_configured_stats(self):
        app_config = DummyConfig(
            {
                "channel": {
                    "name_template": "{icon} {title}: {value}",
                    "type": "voice",
                    "showed_stats": [
                        {"key": "users", "icon": "👥", "title": "Users", "value": "get_user_count"},
                        {"key": "movies", "icon": "🎬", "title": "Movies", "value": "get_movie_count"},
                        {"key": "series", "icon": "📺", "title": "Series", "value": "get_series_count"},
                    ],
                },
                "category": {"use": False, "name": "Stats"},
            }
        )
        manager = DiscordChannelManager(app_config, FakeStatsProvider())

        specs = manager.get_configured_channel_specs()

        self.assertEqual(len(specs), 2)
        self.assertEqual(specs[0]["name"], "👥 Users: 5")
        self.assertEqual(specs[1]["name"], "🎬 Movies: 12")

    def test_channel_manager_persists_channel_ids(self):
        app_config = DummyConfig({"channel": {"showed_stats": []}, "category": {"use": False}})

        with tempfile.TemporaryDirectory() as tmp_dir:
            storage_path = Path(tmp_dir) / "channels.json"
            manager = DiscordChannelManager(app_config, FakeStatsProvider(), storage_path=storage_path)

            manager._remember_channel(123, "users", 999)
            manager._save_storage()

            with open(storage_path, "r", encoding="utf-8") as file:
                data = json.load(file)

            self.assertEqual(data["guilds"]["123"]["users"], 999)
            self.assertEqual(manager._get_persisted_channel_id(123, "users"), 999)

    def test_channel_manager_builds_private_overwrites(self):
        app_config = DummyConfig({"channel": {"showed_stats": [], "private": True}, "category": {"use": False}})
        manager = DiscordChannelManager(app_config, FakeStatsProvider())

        guild = type(
            "FakeGuild",
            (),
            {
                "default_role": object(),
                "me": object(),
            },
        )()

        overwrites = manager._get_permission_overwrites(guild)

        self.assertIsNotNone(overwrites)
        self.assertEqual(len(overwrites), 2)


if __name__ == "__main__":
    print("Running project checks...\n")
    unittest.main(verbosity=2)
