from typing import List, Literal, Optional
from pydantic import BaseModel, Field

MetadataSource = Literal["igdb", "steam"]


class IgdbCredentials(BaseModel):
    """Credenciais do app da Twitch; vazias = usa as do .env (ou só a Steam, sem IGDB)."""
    igdb_client_id: Optional[str] = None
    igdb_client_secret: Optional[str] = None


class MetadataSearchRequest(IgdbCredentials):
    title: str = Field(max_length=200)


class MetadataCandidate(BaseModel):
    source: MetadataSource
    source_id: str
    name: str
    year: Optional[int] = None
    platforms: List[str] = []


class MetadataSearchResponse(BaseModel):
    candidates: List[MetadataCandidate]
    warning: Optional[str] = None  # ex.: credenciais da IGDB recusadas, resultado veio da Steam


class MetadataDetailsRequest(IgdbCredentials):
    source: MetadataSource
    source_id: str = Field(min_length=1, max_length=40)
    title: str = Field(max_length=200)  # usado na busca do HowLongToBeat


class MetadataProposal(BaseModel):
    """Valores sugeridos, já na grafia do GameRoom quando batem com algo cadastrado."""
    source: MetadataSource
    name: str
    year: Optional[int] = None
    developer: Optional[str] = None
    franchise: Optional[str] = None
    genres: List[str] = []  # no máximo 2: principal e secundário
    platforms: List[str] = []  # só plataformas já cadastradas
    hltb_hours: Optional[float] = None
    hltb_source: Optional[str] = None
