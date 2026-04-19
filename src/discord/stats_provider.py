class JellyfinStatsProvider:
    def __init__(self, jellyfin_service, playback_reporting, function_config):
        self.jellyfin_service = jellyfin_service
        self.playback_reporting = playback_reporting
        self.function_config = function_config
        self._handlers = {
            "get_user_count": self.get_user_count,
            "get_online_user_count": self.get_online_user_count,
            "get_movie_count": self.get_movie_count,
            "get_series_count": self.get_series_count,
            "get_episode_count": self.get_episode_count,
            "get_movie_watch_count": self.get_movie_watch_count,
            "get_series_watch_count": self.get_series_watch_count,
            "get_episode_watch_count": self.get_episode_watch_count,
            "get_top_movies": self.get_top_movies,
            "get_top_series": self.get_top_series,
            "get_total_watch_time": self.get_total_watch_time,
        }

    def get_enabled_function_keys(self):
        return {
            item.get("key")
            for item in self.function_config.get("functions", [])
            if item.get("enabled")
        }

    def is_enabled(self, function_key):
        return function_key in self.get_enabled_function_keys()

    def get_stat_value(self, function_key):
        if not self.is_enabled(function_key):
            return "disabled"

        handler = self._handlers.get(function_key)
        if handler is None:
            return "n/a"

        try:
            return handler()
        except Exception as exc:
            print(f"Failed to resolve stat '{function_key}': {exc}")
            return "n/a"

    def get_user_count(self):
        return len(self.jellyfin_service.get_all_users())

    def get_online_user_count(self):
        return len(self.jellyfin_service.get_active_sessions())

    def get_movie_count(self):
        return len(self.jellyfin_service.get_all_movies())

    def get_series_count(self):
        return len(self.jellyfin_service.get_all_tv_shows())

    def get_episode_count(self):
        return len(self.jellyfin_service.get_all_episodes())

    def get_movie_watch_count(self):
        return self.playback_reporting.get_item_play_count("Movie")

    def get_series_watch_count(self):
        return self.playback_reporting.get_item_play_count("Series")

    def get_episode_watch_count(self):
        return self.playback_reporting.get_item_play_count("Episode")

    def get_top_movies(self):
        return self.playback_reporting.get_top_items("Movie")

    def get_top_series(self):
        return self.playback_reporting.get_top_items("Series")

    def get_total_watch_time(self):
        return self.playback_reporting.get_total_watch_time()
