from fastapi import APIRouter
from backend.app.api.v1.endpoints import games, genres, platforms, franchises, developers, stats, uploads

api_router = APIRouter()

api_router.include_router(games.router, prefix="/games", tags=["Jogos"])
api_router.include_router(genres.router, prefix="/genres", tags=["Gêneros"])
api_router.include_router(platforms.router, prefix="/platforms", tags=["Plataformas"])
api_router.include_router(franchises.router, prefix="/franchises", tags=["Franquias"])
api_router.include_router(developers.router, prefix="/developers", tags=["Desenvolvedoras"])
api_router.include_router(stats.router, prefix="/stats", tags=["Estatísticas"])
api_router.include_router(uploads.router, prefix="/uploads", tags=["Uploads"])
