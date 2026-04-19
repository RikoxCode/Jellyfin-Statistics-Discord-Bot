import requests

class JellyfinClient:
    def __init__(self, base_url, api_key, timeout=10):
        if not base_url:
            raise ValueError("JELLYFIN_SERVER_URL is not configured.")
        if not api_key:
            raise ValueError("JELLYFIN_API_KEY is not configured.")

        self.base_url = base_url
        self.api_key = api_key
        self.timeout = timeout

    def get_headers(self):
        return {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-Emby-Token": self.api_key,
            "Authorization": f"MediaBrowser Token={self.api_key}",
        }

    def get_url(self, endpoint):
        return f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"

    def get_request_timeout(self):
        return self.timeout

    def request(self, endpoint, method="GET", body=None, params=None):
        url = self.get_url(endpoint)
        headers = self.get_headers()

        if method.upper() == "POST":
            response = requests.post(url, headers=headers, json=body, timeout=self.timeout)
        else:
            response = requests.get(url, headers=headers, params=params, timeout=self.timeout)

        response.raise_for_status()
        return response.json()


class JellyfinService:
    def __init__(self, client):
        self.client = client

    def get_health(self):
        try:
            self.client.request("/System/Info")
            return True
        except requests.RequestException:
            return False

    def get_all_users(self):
        return self.client.request("/Users") or []

    def get_active_sessions(self):
        return self.client.request("/Sessions") or []

    def get_all_items(self):
        response = self.client.request("/Items", params={"Recursive": True})
        return response.get("Items", []) if isinstance(response, dict) else response or []

    def get_all_movies(self):
        response = self.client.request("/Items", params={"IncludeItemTypes": "Movie", "Recursive": True})
        return response.get("Items", []) if isinstance(response, dict) else []

    def get_all_tv_shows(self):
        response = self.client.request("/Items", params={"IncludeItemTypes": "Series", "Recursive": True})
        return response.get("Items", []) if isinstance(response, dict) else []

    def get_all_episodes(self):
        response = self.client.request("/Items", params={"IncludeItemTypes": "Episode", "Recursive": True})
        return response.get("Items", []) if isinstance(response, dict) else []