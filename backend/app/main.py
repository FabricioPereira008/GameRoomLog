from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from backend.app.core.config import settings
from backend.app.core.database import engine, Base
from backend.app.api.v1.api_router import api_router

# Criar tabelas no banco de dados automaticamente se não existirem
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="API do GameRoomLog para gerenciamento de backlog de jogos e anuário"
)

# Configuração de CORS (liberado para facilitar integrações desktop/mobile)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Montar diretório estático para capas
app.mount("/static/covers", StaticFiles(directory=settings.COVERS_DIR), name="covers")

# Incluir rotas da API v1
app.include_router(api_router, prefix=settings.API_V1_STR)

@app.get("/")
def root():
    return {
        "message": "GameRoomLog API está online!",
        "docs": "/docs",
        "version": settings.VERSION
    }
