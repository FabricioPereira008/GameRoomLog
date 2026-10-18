"""Provedor Steam: lista os jogos da conta via Web API oficial (GetOwnedGames)."""
import logging
from typing import List, Optional

import httpx

from backend.app.services.library.base import LibraryEntry, LibraryProviderError
from backend.app.services.library.settings_store import load_settings

# A key vai na query string; o httpx loga a URL completa em INFO
logging.getLogger("httpx").setLevel(logging.WARNING)

OWNED_GAMES_URL = "https://api.steampowered.com/IPlayerService/GetOwnedGames/v1/"
TIMEOUT = 20.0


APP_DETAILS_URL = "https://store.steampowered.com/api/appdetails"


def fetch_app_developer(appid: str) -> Optional[str]:
    """Desenvolvedora de um app pela API pública da loja (sem key). None se não der para saber."""
    if not appid.isdigit():
        return None
    try:
        res = httpx.get(APP_DETAILS_URL, params={"appids": appid, "l": "brazilian"}, timeout=10.0)
        data = res.json().get(appid, {}) if res.status_code == 200 else {}
    except (httpx.HTTPError, ValueError):
        logging.getLogger(__name__).warning("Falha ao consultar detalhes do app %s na Steam", appid)
        return None
    developers = (data.get("data") or {}).get("developers") if data.get("success") else None
    if isinstance(developers, list) and developers and isinstance(developers[0], str):
        return developers[0].strip() or None
    return None


class SteamProvider:
    store = "steam"

    def fetch(self) -> List[LibraryEntry]:
        cfg = load_settings()
        if not cfg.steam_api_key or not cfg.steam_id:
            raise LibraryProviderError("Informe a Steam API key e o SteamID64 nas configurações.")
        params = {
            "key": cfg.steam_api_key,
            "steamid": cfg.steam_id,
            "include_appinfo": 1,
            "include_played_free_games": 1,
            "format": "json",
        }
        try:
            res = httpx.get(OWNED_GAMES_URL, params=params, timeout=TIMEOUT)
        except httpx.HTTPError as exc:  # a mensagem do httpx pode conter a URL (com a key)
            logging.getLogger(__name__).warning("Falha de rede ao consultar a Steam: %s", type(exc).__name__)
            raise LibraryProviderError("Não foi possível conectar à Steam.") from None
        if res.status_code in (401, 403):
            raise LibraryProviderError("Steam API key inválida ou sem permissão.")
        if res.status_code != 200:
            raise LibraryProviderError(f"A Steam respondeu com erro {res.status_code}.")
        try:
            games = res.json().get("response", {}).get("games")
        except ValueError:
            raise LibraryProviderError("Resposta inesperada da Steam.") from None
        if games is None:
            raise LibraryProviderError(
                "A Steam não retornou jogos: verifique o SteamID64 e se os detalhes dos jogos do perfil estão públicos."
            )
        entries = []
        for game in games:
            appid, name = game.get("appid"), (game.get("name") or "").strip()
            if appid is None or not name:
                continue
            hours = round((game.get("playtime_forever") or 0) / 60, 1)
            entries.append(LibraryEntry("steam", str(appid), name, hours))
        return entries
