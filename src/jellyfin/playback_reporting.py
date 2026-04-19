class PlaybackReporting:
    def __init__(self, client):
        self.client = client

    def _run_query(self, query):
        result = self.client.request(
            "/user_usage_stats/submit_custom_query",
            method="POST",
            body={"CustomQueryString": query, "ReplaceUserId": False},
        )
        if isinstance(result, dict):
            return result.get("results", [])
        return []

    def _get_first_value(self, rows, default=0):
        if rows and isinstance(rows[0], (list, tuple)) and len(rows[0]) > 1:
            return rows[0][1]
        return default

    def get_movie_watch_time(self):
        query = """
        SELECT 
            ItemType,
            ROUND(SUM(PlayDuration) / 3600.0, 2) AS TotalHours
        FROM PlaybackActivity
        WHERE ItemType = 'Movie'
        GROUP BY ItemType
        """
        return self._get_first_value(self._run_query(query), 0)

    def get_tv_show_watch_time(self):
        query = """
        SELECT 
            ItemType,
            ROUND(SUM(PlayDuration) / 3600.0, 2) AS TotalHours
        FROM PlaybackActivity
        WHERE ItemType = 'Episode'
        GROUP BY ItemType
        """
        return self._get_first_value(self._run_query(query), 0)

    def get_total_watch_time(self):
        query = """
        SELECT 
            'Total' AS ItemType,
            ROUND(SUM(PlayDuration) / 3600.0, 2) AS TotalHours
        FROM PlaybackActivity
        """
        return self._get_first_value(self._run_query(query), 0)

    def get_item_play_count(self, item_type):
        query = f"""
        SELECT 
            ItemType,
            COUNT(*) AS PlayCount
        FROM PlaybackActivity
        WHERE ItemType = '{item_type}'
        GROUP BY ItemType
        """
        return int(self._get_first_value(self._run_query(query), 0) or 0)

    def get_top_items(self, item_type, limit=3):
        safe_limit = max(int(limit), 1)
        query = f"""
        SELECT 
            ItemName,
            COUNT(*) AS PlayCount
        FROM PlaybackActivity
        WHERE ItemType = '{item_type}'
        GROUP BY ItemName
        ORDER BY PlayCount DESC
        LIMIT {safe_limit}
        """
        rows = self._run_query(query)
        return [row[0] for row in rows if row and row[0]]