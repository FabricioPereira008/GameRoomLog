import requests
from typing import List, Dict, Any, Optional
from pathlib import Path

class ApiClient:
    def __init__(self, base_url: str = "http://127.0.0.1:8000/api/v1"):
        self.base_url = base_url.rstrip("/")

    def _url(self, path: str) -> str:
        return f"{self.base_url}/{path.lstrip('/')}"

    def is_backend_online(self) -> bool:
        try:
            r = requests.get(f"{self.base_url.replace('/api/v1', '')}/", timeout=2)
            return r.status_code == 200
        except Exception:
            return False

    # --- JOGOS ---
    def get_games(
        self,
        status: Optional[str] = None,
        platform_id: Optional[int] = None,
        genre_id: Optional[int] = None,
        completion_year: Optional[int] = None,
        is_favorite: Optional[bool] = None,
        search: Optional[str] = None,
        sort_by: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        params = {}
        if status:
            params["status"] = status
        if platform_id:
            params["platform_id"] = platform_id
        if genre_id:
            params["genre_id"] = genre_id
        if completion_year:
            params["completion_year"] = completion_year
        if is_favorite is not None:
            params["is_favorite"] = is_favorite
        if search:
            params["search"] = search
        if sort_by:
            params["sort_by"] = sort_by

        r = requests.get(self._url("games/"), params=params, timeout=5)
        r.raise_for_status()
        return r.json()

    def get_game(self, game_id: int) -> Dict[str, Any]:
        r = requests.get(self._url(f"games/{game_id}"), timeout=5)
        r.raise_for_status()
        return r.json()

    def create_game(self, data: Dict[str, Any]) -> Dict[str, Any]:
        r = requests.post(self._url("games/"), json=data, timeout=5)
        r.raise_for_status()
        return r.json()

    def update_game(self, game_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        r = requests.put(self._url(f"games/{game_id}"), json=data, timeout=5)
        r.raise_for_status()
        return r.json()

    def delete_game(self, game_id: int) -> bool:
        r = requests.delete(self._url(f"games/{game_id}"), timeout=5)
        return r.status_code == 204

    # --- UPLOAD DE CAPA ---
    def upload_cover(self, file_path: str) -> Optional[str]:
        path = Path(file_path)
        if not path.exists():
            return None
        with open(path, "rb") as f:
            files = {"file": (path.name, f, "image/jpeg")}
            r = requests.post(self._url("uploads/cover"), files=files, timeout=10)
            if r.status_code == 200:
                return r.json().get("filename")
        return None

    # --- GÊNEROS ---
    def get_genres(self) -> List[Dict[str, Any]]:
        r = requests.get(self._url("genres/"), timeout=5)
        r.raise_for_status()
        return r.json()

    def create_genre(self, name: str, color: str = "#4A5568") -> Dict[str, Any]:
        r = requests.post(self._url("genres/"), json={"name": name, "color": color}, timeout=5)
        r.raise_for_status()
        return r.json()

    # --- PLATAFORMAS ---
    def get_platforms(self) -> List[Dict[str, Any]]:
        r = requests.get(self._url("platforms/"), timeout=5)
        r.raise_for_status()
        return r.json()

    def create_platform(self, name: str, icon_name: Optional[str] = None) -> Dict[str, Any]:
        r = requests.post(self._url("platforms/"), json={"name": name, "icon_name": icon_name}, timeout=5)
        r.raise_for_status()
        return r.json()

    # --- FRANQUIAS ---
    def get_franchises(self) -> List[Dict[str, Any]]:
        r = requests.get(self._url("franchises/"), timeout=5)
        r.raise_for_status()
        return r.json()

    def create_franchise(self, name: str) -> Dict[str, Any]:
        r = requests.post(self._url("franchises/"), json={"name": name}, timeout=5)
        r.raise_for_status()
        return r.json()

    # --- ESTATÍSTICAS E ANUÁRIO ---
    def get_yearbook(self, year: int) -> Dict[str, Any]:
        r = requests.get(self._url(f"stats/yearbook/{year}"), timeout=5)
        r.raise_for_status()
        return r.json()

    def get_overall_stats(self) -> Dict[str, Any]:
        r = requests.get(self._url("stats/overall"), timeout=5)
        r.raise_for_status()
        return r.json()

api_client = ApiClient()
