from backend.app.schemas.genre import GenreBase, GenreCreate, GenreUpdate, GenreResponse
from backend.app.schemas.platform import PlatformBase, PlatformCreate, PlatformUpdate, PlatformResponse
from backend.app.schemas.franchise import FranchiseBase, FranchiseCreate, FranchiseUpdate, FranchiseResponse
from backend.app.schemas.developer import DeveloperBase, DeveloperCreate, DeveloperUpdate, DeveloperResponse
from backend.app.schemas.game import GameBase, GameCreate, GameUpdate, GameResponse
from backend.app.schemas.stats import YearbookSummary, StatusCounts, OverallStats

__all__ = [
    "GenreBase", "GenreCreate", "GenreUpdate", "GenreResponse",
    "PlatformBase", "PlatformCreate", "PlatformUpdate", "PlatformResponse",
    "FranchiseBase", "FranchiseCreate", "FranchiseUpdate", "FranchiseResponse",
    "DeveloperBase", "DeveloperCreate", "DeveloperUpdate", "DeveloperResponse",
    "GameBase", "GameCreate", "GameUpdate", "GameResponse",
    "YearbookSummary", "StatusCounts", "OverallStats"
]
