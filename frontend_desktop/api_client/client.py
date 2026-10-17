import os
import sys
import requests
from typing import List, Dict, Any, Optional
from pathlib import Path

DEFAULT_BASE_URL = "http://127.0.0.1:8000/api/v1"
DEFAULT_TIMEOUT = 5
UPLOAD_TIMEOUT = 15
IMPORT_TIMEOUT = 120
SCAN_TIMEOUT = 90


def get_default_base_url() -> str:
    """URL da API; pode ser sobrescrita com GAMEROOM_API_URL."""
    return os.environ.get("GAMEROOM_API_URL", DEFAULT_BASE_URL)


def get_cover_cache_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    return base / "gameroomlog" / "covers"


class ApiClient:
    def __init__(self, base_url: Optional[str] = None, cover_cache_dir: Optional[Path] = None):
        self.base_url = (base_url or get_default_base_url()).rstrip("/")
        self.cover_cache_dir = cover_cache_dir
        self._session = requests.Session()

    def _url(self, path: str) -> str:
        return f"{self.base_url}/{path.lstrip('/')}"

    @property
    def server_url(self) -> str:
        return self.base_url.replace("/api/v1", "")

    def _request(self, method: str, path: str, timeout: float = DEFAULT_TIMEOUT, **kwargs) -> requests.Response:
        return self._session.request(method, self._url(path), timeout=timeout, **kwargs)

    def _json(self, method: str, path: str, timeout: float = DEFAULT_TIMEOUT, **kwargs) -> Any:
        r = self._request(method, path, timeout=timeout, **kwargs)
        r.raise_for_status()
        return r.json()

    def _delete(self, path: str) -> bool:
        return self._request("DELETE", path).status_code == 204

    def is_backend_online(self) -> bool:
        """True só se o servidor responder e for a API do GameRoomLog (não outro serviço na porta)."""
        try:
            r = self._session.get(f"{self.server_url}/", timeout=2)
            return r.status_code == 200 and "GameRoomLog" in r.text
        except Exception:
            return False

    def get_cover_path(self, filename: str) -> Optional[str]:
        """Baixa a capa do backend (uma vez) e retorna o caminho do arquivo em cache local."""
        safe_name = Path(filename).name
        if not safe_name:
            return None
        cache_dir = self.cover_cache_dir or get_cover_cache_dir()
        target = cache_dir / safe_name
        if target.exists():
            return str(target)
        try:
            r = self._session.get(f"{self.server_url}/static/covers/{safe_name}", timeout=DEFAULT_TIMEOUT)
            if r.status_code != 200:
                return None
            cache_dir.mkdir(parents=True, exist_ok=True)
            target.write_bytes(r.content)
            return str(target)
        except Exception:
            return None

    # --- JOGOS ---
    def get_games(
        self,
        status: Optional[str] = None,
        platform_id: Optional[int] = None,
        genre_id: Optional[int] = None,
        franchise_id: Optional[int] = None,
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
        if franchise_id:
            params["franchise_id"] = franchise_id
        if completion_year:
            params["completion_year"] = completion_year
        if is_favorite is not None:
            params["is_favorite"] = is_favorite
        if search:
            params["search"] = search
        if sort_by:
            params["sort_by"] = sort_by

        return self._json("GET", "games/", params=params)

    def get_game(self, game_id: int) -> Dict[str, Any]:
        return self._json("GET", f"games/{game_id}")

    def create_game(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return self._json("POST", "games/", json=data)

    def update_game(self, game_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        return self._json("PUT", f"games/{game_id}", json=data)

    def delete_game(self, game_id: int) -> bool:
        return self._delete(f"games/{game_id}")

    # --- UPLOAD E DOWNLOAD DE CAPA ---
    def upload_cover(self, file_path: str) -> Optional[str]:
        path = Path(file_path)
        if not path.exists():
            return None
        with open(path, "rb") as f:
            files = {"file": (path.name, f, "image/jpeg")}
            r = self._request("POST", "uploads/cover", timeout=UPLOAD_TIMEOUT, files=files)
            if r.status_code == 200:
                return r.json().get("filename")
        return None

    def upload_cover_url(self, url: str) -> Optional[str]:
        r = self._request("POST", "uploads/cover-url", timeout=UPLOAD_TIMEOUT, json={"url": url})
        if r.status_code == 200:
            return r.json().get("filename")
        return None

    def auto_search_cover(self, title: str, api_key: Optional[str] = None) -> Optional[str]:
        payload = {"title": title}
        if api_key:
            payload["api_key"] = api_key
        r = self._request("POST", "uploads/auto-cover", timeout=UPLOAD_TIMEOUT, json=payload)
        if r.status_code == 200:
            return r.json().get("filename")
        return None

    # --- GÊNEROS ---
    def get_genres(self) -> List[Dict[str, Any]]:
        return self._json("GET", "genres/")

    def get_genre_details(self, genre_id: int) -> Dict[str, Any]:
        return self._json("GET", f"genres/{genre_id}/details")

    def create_genre(self, name: str, color: str = "#4A5568") -> Dict[str, Any]:
        return self._json("POST", "genres/", json={"name": name, "color": color})

    def update_genre(self, genre_id: int, name: str, color: str) -> Dict[str, Any]:
        return self._json("PUT", f"genres/{genre_id}", json={"name": name, "color": color})

    def delete_genre(self, genre_id: int) -> bool:
        return self._delete(f"genres/{genre_id}")

    # --- PLATAFORMAS ---
    def get_platforms(self) -> List[Dict[str, Any]]:
        return self._json("GET", "platforms/")

    def get_platform_details(self, platform_id: int) -> Dict[str, Any]:
        return self._json("GET", f"platforms/{platform_id}/details")

    def create_platform(self, name: str, icon_name: Optional[str] = None) -> Dict[str, Any]:
        return self._json("POST", "platforms/", json={"name": name, "icon_name": icon_name})

    def update_platform(self, platform_id: int, name: str, icon_name: Optional[str] = None) -> Dict[str, Any]:
        return self._json("PUT", f"platforms/{platform_id}", json={"name": name, "icon_name": icon_name})

    def delete_platform(self, platform_id: int) -> bool:
        return self._delete(f"platforms/{platform_id}")

    # --- FRANQUIAS ---
    def get_franchises(self) -> List[Dict[str, Any]]:
        return self._json("GET", "franchises/")

    def get_franchise_details(self, franchise_id: int) -> Dict[str, Any]:
        return self._json("GET", f"franchises/{franchise_id}/details")

    def create_franchise(self, name: str) -> Dict[str, Any]:
        return self._json("POST", "franchises/", json={"name": name})

    def update_franchise(self, franchise_id: int, name: str) -> Dict[str, Any]:
        return self._json("PUT", f"franchises/{franchise_id}", json={"name": name})

    def delete_franchise(self, franchise_id: int) -> bool:
        return self._delete(f"franchises/{franchise_id}")

    # --- DESENVOLVEDORAS ---
    def get_developers(self) -> List[Dict[str, Any]]:
        return self._json("GET", "developers/")

    def create_developer(self, name: str) -> Dict[str, Any]:
        return self._json("POST", "developers/", json={"name": name})

    def update_developer(self, dev_id: int, name: str) -> Dict[str, Any]:
        return self._json("PUT", f"developers/{dev_id}", json={"name": name})

    def delete_developer(self, dev_id: int) -> bool:
        return self._delete(f"developers/{dev_id}")

    # --- ESTATÍSTICAS E ANUÁRIO ---
    def get_yearbook(self, year: int) -> Dict[str, Any]:
        return self._json("GET", f"stats/yearbook/{year}")

    def get_overall_stats(self) -> Dict[str, Any]:
        return self._json("GET", "stats/overall")

    # --- IMPORTAÇÃO DO NOTION ---
    def import_notion(self, folder_path: str, auto_fetch_covers: bool = True) -> Dict[str, Any]:
        return self._json(
            "POST", "imports/notion", timeout=IMPORT_TIMEOUT,
            json={"folder_path": folder_path, "auto_fetch_covers": auto_fetch_covers},
        )

    # --- CAPAS AUTOMÁTICAS ---
    def auto_cover_game(self, game_id: int, api_key: Optional[str] = None) -> Dict[str, Any]:
        return self._json(
            "POST", f"uploads/auto-cover-game/{game_id}", timeout=20,
            json={"api_key": api_key} if api_key else {},
        )

    # --- SINCRONIZAÇÃO DE BIBLIOTECAS (Steam, Heroic...) ---
    def library_scan(self, include_all: bool = False, stores: Optional[List[str]] = None) -> Dict[str, Any]:
        return self._json("POST", "library/scan", timeout=SCAN_TIMEOUT,
                          json={"include_all": include_all, "stores": stores})

    def library_import(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        return self._json("POST", "library/import", timeout=IMPORT_TIMEOUT, json={"items": items})

    def library_ignore(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        return self._json("POST", "library/ignored", json={"items": items})

    def library_ignored(self) -> List[Dict[str, Any]]:
        return self._json("GET", "library/ignored")

    def library_unignore(self, ignored_id: int) -> bool:
        return self._delete(f"library/ignored/{ignored_id}")

    def get_library_settings(self) -> Dict[str, Any]:
        return self._json("GET", "library/settings")

    def save_library_settings(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return self._json("PUT", "library/settings", json=data)


api_client = ApiClient()
