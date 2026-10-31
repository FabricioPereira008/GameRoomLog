"""Busca automática de dados de um jogo (desenvolvedora, franquia, gêneros, plataformas e duração).

Fontes: IGDB (principal; precisa de um app da Twitch), Steam (sem chave, quando não há IGDB ou ela
não acha o jogo) e HowLongToBeat (duração; sem API oficial, então qualquer falha é ignorada e a
duração vem do "time to beat" da IGDB). Nada é gravado aqui: a GUI mostra a proposta e o usuário
escolhe o que aplicar.
"""
import asyncio
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Tuple

import httpx
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.models.developer import Developer
from backend.app.models.franchise import Franchise
from backend.app.models.genre import Genre
from backend.app.models.platform import Platform
from backend.app.schemas.metadata import MetadataCandidate, MetadataProposal, MetadataSearchResponse
from backend.app.services.inbox_service import match_key, similarity
from backend.app.services.library.steam import APP_DETAILS_URL
from backend.app.services.library_service import clean_developer, looks_like_non_game, normalize_title

logger = logging.getLogger(__name__)

TWITCH_TOKEN_URL = "https://id.twitch.tv/oauth2/token"
IGDB_URL = "https://api.igdb.com/v4"
STEAM_SEARCH_URL = "https://store.steampowered.com/api/storesearch/"
HTTP_TIMEOUT = 12.0
HLTB_TIMEOUT = 20.0
MAX_CANDIDATES = 8
MAX_GENRES = 2
FRANCHISE_THRESHOLD = 85
HLTB_MIN_SIMILARITY = 0.6

IGDB_SEARCH_FIELDS = "name,first_release_date,platforms.name"
IGDB_DETAIL_FIELDS = (
    "name,first_release_date,platforms.name,genres.name,themes.name,keywords.name,"
    "player_perspectives.name,involved_companies.developer,involved_companies.company.name,"
    "franchises.name,collections.name"
)

# Nome da plataforma na IGDB/Steam -> nome curto usado no GameRoom (depois casado com o cadastro)
PLATFORM_ALIASES = {
    "pc (microsoft windows)": "PC", "linux": "PC", "mac": "PC", "steamos": "PC",
    "nintendo switch": "Switch", "nintendo switch 2": "Switch 2", "nintendo 3ds": "3DS",
    "new nintendo 3ds": "3DS", "nintendo ds": "DS", "nintendo 64": "N64", "wii u": "Wii U",
    "playstation": "PS1", "playstation 2": "PS2", "playstation 3": "PS3", "playstation 4": "PS4",
    "playstation 5": "PS5", "playstation portable": "PSP", "playstation vita": "PS Vita",
    "xbox series x|s": "Xbox Series", "game boy advance": "GBA",
    "super nintendo entertainment system": "SNES", "nintendo entertainment system": "NES",
}


# Um gênero composto já diz o que o genérico diria; não vale como secundário
_COVERED_BY = {
    "Ação e Aventura": {"Ação", "Aventura"},
    "RPG de Ação": {"RPG", "Ação"},
    "RPG por Turnos": {"RPG"},
    "Aventura Narrativa": {"Aventura"},
    "FPS": {"Ação"},
}


class MetadataSourceError(Exception):
    """A fonte respondeu com erro (rede, credenciais, limite de uso)."""


class MetadataNotFoundError(Exception):
    pass


@dataclass
class KnownNames:
    """Nomes já cadastrados, para devolver a grafia do GameRoom e não criar duplicatas."""
    developers: Dict[str, str] = field(default_factory=dict)  # normalize_title -> nome
    franchises: List[str] = field(default_factory=list)
    genres: Dict[str, str] = field(default_factory=dict)  # match_key -> nome
    platforms: Dict[str, str] = field(default_factory=dict)  # match_key -> nome


def load_known_names(db: Session) -> KnownNames:
    return KnownNames(
        developers={normalize_title(n): n for (n,) in db.query(Developer.name)},
        franchises=[n for (n,) in db.query(Franchise.name)],
        genres={match_key(n): n for (n,) in db.query(Genre.name)},
        platforms={match_key(n): n for (n,) in db.query(Platform.name)},
    )


# --- mapeamento de gêneros para a taxonomia do GameRoom ---

def _has(words: Iterable[str], *needles: str) -> bool:
    return any(n in w for w in words for n in needles)


def map_genres(genres: Iterable[str], themes: Iterable[str] = (), keywords: Iterable[str] = (),
               perspectives: Iterable[str] = ()) -> List[str]:
    """Converte gêneros/temas/palavras-chave (IGDB ou Steam, em inglês) em até 2 gêneros da taxonomia,
    do mais específico para o mais genérico."""
    g = {s.lower() for s in genres}
    t = {s.lower() for s in themes}
    k = {s.lower() for s in keywords}
    p = {s.lower() for s in perspectives}
    rpg = _has(g, "role-playing", "rpg")
    action = "action" in t or "action" in g
    shooter = "shooter" in g

    rules: List[Tuple[bool, str]] = [
        (_has(k, "soulslike", "souls-like"), "Soulslike"),
        (_has(k, "metroidvania"), "Metroidvania"),
        (_has(k, "roguelike", "roguelite", "rogue-lite", "rogue-like"), "Roguelike"),
        (_has(g, "visual novel"), "Visual Novel"),
        (_has(k, "tower defense"), "Tower Defense"),
        (_has(k, "shoot 'em up", "shmup", "bullet hell"), "Shoot 'em up"),
        (shooter and "first person" in p, "FPS"),
        (_has(g, "fighting"), "Luta"),
        (_has(k, "beat 'em up", "brawler"), "Beat 'em up"),
        (rpg and _has(g, "turn-based"), "RPG por Turnos"),
        (rpg and _has(g, "tactical"), "Tático"),
        (rpg and (action or _has(g, "hack and slash")), "RPG de Ação"),
        (rpg, "RPG"),
        ("horror" in t, "Terror"),
        ("stealth" in t, "Stealth"),
        ("survival" in t, "Sobrevivência"),
        (_has(g, "hack and slash"), "Hack and Slash"),
        (_has(g, "platform"), "Plataforma"),
        (_has(g, "music", "rhythm"), "Ritmo"),
        (_has(g, "racing"), "Corrida"),
        (_has(g, "sport"), "Esporte"),
        (_has(g, "puzzle"), "Puzzle"),
        (_has(g, "card & board", "card game"), "Cartas"),
        (_has(g, "tactical"), "Tático"),
        ("business" in t or _has(k, "city builder", "management"), "Gestão e Construção"),
        (_has(g, "strategy", "rts", "tbs", "moba"), "Estratégia"),
        (_has(g, "simulat"), "Simulação"),
        ("sandbox" in t, "Sandbox"),
        (_has(g, "point-and-click"), "Aventura"),
        (_has(g, "adventure") and _has(t, "drama", "mystery") and not action, "Aventura Narrativa"),
        (_has(g, "adventure") and action, "Ação e Aventura"),
        (_has(g, "adventure"), "Aventura"),
        (_has(g, "arcade", "pinball"), "Arcade"),
        (action or shooter, "Ação"),
    ]
    picked: List[str] = []
    for matched, name in rules:
        covered = any(name in _COVERED_BY.get(prev, ()) for prev in picked)
        if matched and name not in picked and not covered:
            picked.append(name)
        if len(picked) == MAX_GENRES:
            break
    return picked


def _known_genres(names: List[str], known: KnownNames) -> List[str]:
    return [known.genres.get(match_key(n), n) for n in names]


def _known_platforms(names: Iterable[str], known: KnownNames) -> List[str]:
    """Só plataformas já cadastradas (o campo da plataforma não aceita texto livre)."""
    found: List[str] = []
    for name in names:
        short = PLATFORM_ALIASES.get(name.strip().lower(), name)
        existing = known.platforms.get(match_key(short))
        if existing and existing not in found:
            found.append(existing)
    return found


def _known_franchise(name: Optional[str], known: KnownNames) -> Optional[str]:
    if not name:
        return None
    key = match_key(name)
    best = max(known.franchises, key=lambda f: similarity(key, match_key(f)), default=None)
    if best and similarity(key, match_key(best)) >= FRANCHISE_THRESHOLD:
        return best
    return name


def _year_from_timestamp(ts) -> Optional[int]:
    return time.gmtime(ts).tm_year if isinstance(ts, (int, float)) else None


def _names(items) -> List[str]:
    return [i["name"] for i in items or [] if isinstance(i, dict) and i.get("name")]


# --- IGDB ---

_token_cache: Dict[str, Tuple[str, float]] = {}  # client_id -> (token, expira em)


def resolve_credentials(client_id: Optional[str], secret: Optional[str]) -> Optional[Tuple[str, str]]:
    client_id = (client_id or "").strip() or settings.IGDB_CLIENT_ID.strip()
    secret = (secret or "").strip() or settings.IGDB_CLIENT_SECRET.strip()
    return (client_id, secret) if client_id and secret else None


async def _igdb_token(client: httpx.AsyncClient, creds: Tuple[str, str]) -> str:
    client_id, secret = creds
    cached = _token_cache.get(client_id)
    if cached and cached[1] > time.time():
        return cached[0]
    res = await client.post(TWITCH_TOKEN_URL, params={
        "client_id": client_id, "client_secret": secret, "grant_type": "client_credentials"})
    if res.status_code != 200:
        raise MetadataSourceError("A Twitch recusou as credenciais da IGDB (confira o Client ID e o Secret).")
    data = res.json()
    token = data["access_token"]
    _token_cache[client_id] = (token, time.time() + int(data.get("expires_in", 3600)) - 60)
    return token


async def _igdb_query(client: httpx.AsyncClient, creds: Tuple[str, str], endpoint: str, body: str) -> list:
    token = await _igdb_token(client, creds)
    res = await client.post(f"{IGDB_URL}/{endpoint}", content=body, headers={
        "Client-ID": creds[0], "Authorization": f"Bearer {token}", "Accept": "application/json"})
    if res.status_code == 401:
        _token_cache.pop(creds[0], None)
    if res.status_code != 200:
        raise MetadataSourceError(f"A IGDB respondeu com erro {res.status_code}.")
    return res.json()


def _igdb_search_body(title: str) -> str:
    escaped = title.replace("\\", " ").replace('"', '\\"')
    return f'search "{escaped}"; fields {IGDB_SEARCH_FIELDS}; limit {MAX_CANDIDATES};'


async def _igdb_candidates(client: httpx.AsyncClient, creds: Tuple[str, str], title: str) -> List[MetadataCandidate]:
    rows = await _igdb_query(client, creds, "games", _igdb_search_body(title))
    return [
        MetadataCandidate(source="igdb", source_id=str(r["id"]), name=r.get("name") or title,
                          year=_year_from_timestamp(r.get("first_release_date")),
                          platforms=_names(r.get("platforms")))
        for r in rows if r.get("id")
    ]


async def _igdb_details(client: httpx.AsyncClient, creds: Tuple[str, str], game_id: str,
                        known: KnownNames) -> Tuple[MetadataProposal, Optional[float]]:
    if not game_id.isdigit():
        raise MetadataNotFoundError()
    rows = await _igdb_query(client, creds, "games", f"fields {IGDB_DETAIL_FIELDS}; where id = {game_id};")
    if not rows:
        raise MetadataNotFoundError()
    g = rows[0]
    developers = [ic["company"]["name"] for ic in g.get("involved_companies") or []
                  if ic.get("developer") and (ic.get("company") or {}).get("name")]
    franchise = next(iter(_names(g.get("franchises")) + _names(g.get("collections"))), None)
    genres = map_genres(_names(g.get("genres")), _names(g.get("themes")),
                        _names(g.get("keywords")), _names(g.get("player_perspectives")))
    proposal = MetadataProposal(
        source="igdb", name=g.get("name") or "", year=_year_from_timestamp(g.get("first_release_date")),
        developer=clean_developer(developers[0], known.developers) if developers else None,
        franchise=_known_franchise(franchise, known),
        genres=_known_genres(genres, known),
        platforms=_known_platforms(_names(g.get("platforms")), known),
    )
    try:
        ttb = await _igdb_query(client, creds, "game_time_to_beats",
                                f"fields normally,hastily; where game_id = {game_id};")
    except MetadataSourceError:
        ttb = []
    seconds = (ttb[0].get("normally") or ttb[0].get("hastily")) if ttb else None
    return proposal, (round(seconds / 3600, 1) if seconds else None)


# --- Steam ---

async def _steam_candidates(client: httpx.AsyncClient, title: str) -> List[MetadataCandidate]:
    res = await client.get(STEAM_SEARCH_URL, params={"term": title, "l": "english", "cc": "BR"})
    items = res.json().get("items", []) if res.status_code == 200 else []
    return [
        MetadataCandidate(source="steam", source_id=str(i["id"]), name=i.get("name") or title, platforms=["PC"])
        for i in items if i.get("id") and not looks_like_non_game(i.get("name") or "")
    ][:MAX_CANDIDATES]


async def _steam_details(client: httpx.AsyncClient, appid: str, known: KnownNames) -> MetadataProposal:
    if not appid.isdigit():
        raise MetadataNotFoundError()
    res = await client.get(APP_DETAILS_URL, params={"appids": appid, "l": "english"})
    if res.status_code != 200:
        raise MetadataSourceError(f"A Steam respondeu com erro {res.status_code}.")
    entry = res.json().get(appid) or {}
    if not entry.get("success"):
        raise MetadataNotFoundError()
    data = entry.get("data") or {}
    developers = [d for d in data.get("developers") or [] if isinstance(d, str) and d.strip()]
    year = re.search(r"\d{4}", (data.get("release_date") or {}).get("date") or "")
    genres = map_genres([g.get("description", "") for g in data.get("genres") or []])
    return MetadataProposal(
        source="steam", name=data.get("name") or "",
        year=int(year.group()) if year else None,
        developer=clean_developer(developers[0], known.developers) if developers else None,
        genres=_known_genres(genres, known),
        platforms=_known_platforms(["PC"], known),
    )


# --- HowLongToBeat ---

async def hltb_main_story(title: str) -> Optional[float]:
    """Horas da história principal no HowLongToBeat (lib não oficial: qualquer falha vira None)."""
    try:
        from howlongtobeatpy import HowLongToBeat
        results = await asyncio.wait_for(HowLongToBeat().async_search(title), HLTB_TIMEOUT)
    except Exception:
        logger.warning("Falha ao consultar o HowLongToBeat para '%s'", title, exc_info=True)
        return None
    best = max((r for r in results or [] if r.main_story), key=lambda r: r.similarity, default=None)
    if best is None or best.similarity < HLTB_MIN_SIMILARITY:
        return None
    return round(float(best.main_story), 1)


# --- API do service ---

def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=HTTP_TIMEOUT, follow_redirects=True)


async def search_candidates(title: str, client_id: Optional[str] = None, secret: Optional[str] = None,
                            client: Optional[httpx.AsyncClient] = None) -> MetadataSearchResponse:
    """Jogos com esse título na IGDB (ou na Steam, sem credenciais ou sem resultado na IGDB)."""
    creds = resolve_credentials(client_id, secret)
    warning = None
    async with (client or _client()) as http:
        candidates: List[MetadataCandidate] = []
        if creds:
            try:
                candidates = await _igdb_candidates(http, creds, title)
            except (MetadataSourceError, httpx.HTTPError) as e:
                warning = f"{e} Resultados da Steam." if isinstance(e, MetadataSourceError) else \
                    "A IGDB não respondeu. Resultados da Steam."
        if not candidates:
            try:
                candidates = await _steam_candidates(http, title)
            except httpx.HTTPError as e:
                raise MetadataSourceError("Não foi possível consultar a Steam.") from e
    if not candidates:
        raise MetadataNotFoundError()
    return MetadataSearchResponse(candidates=candidates, warning=warning)


async def fetch_details(source: str, source_id: str, title: str, known: KnownNames,
                        client_id: Optional[str] = None, secret: Optional[str] = None,
                        client: Optional[httpx.AsyncClient] = None) -> MetadataProposal:
    """Dados do jogo escolhido + duração do HowLongToBeat (consultados em paralelo)."""
    hltb_task = asyncio.ensure_future(hltb_main_story(title))
    igdb_hours = None
    try:
        async with (client or _client()) as http:
            if source == "igdb":
                creds = resolve_credentials(client_id, secret)
                if not creds:
                    raise MetadataSourceError("Informe as credenciais da IGDB nas Configurações.")
                proposal, igdb_hours = await _igdb_details(http, creds, source_id, known)
            else:
                proposal = await _steam_details(http, source_id, known)
    except httpx.HTTPError as e:
        hltb_task.cancel()
        raise MetadataSourceError("A fonte de dados não respondeu.") from e
    except Exception:
        hltb_task.cancel()
        raise
    hours = await hltb_task
    if hours:
        proposal.hltb_hours, proposal.hltb_source = hours, "HowLongToBeat"
    elif igdb_hours:
        proposal.hltb_hours, proposal.hltb_source = igdb_hours, "IGDB"
    return proposal
