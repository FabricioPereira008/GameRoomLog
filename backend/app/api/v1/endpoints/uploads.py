import uuid
import io
import urllib.parse
import httpx
from pathlib import Path
from typing import Optional
from pydantic import BaseModel
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from PIL import Image
from backend.app.core.config import settings

router = APIRouter()

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}

class CoverUrlRequest(BaseModel):
    url: str

class AutoCoverRequest(BaseModel):
    title: str
    api_key: Optional[str] = None

@router.post("/cover")
async def upload_cover(file: UploadFile = File(...)):
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Formato de imagem inválido. Suportados: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    filename = f"{uuid.uuid4()}{ext}"
    destination = settings.COVERS_DIR / filename

    content = await file.read()
    with open(destination, "wb") as f:
        f.write(content)

    return {
        "filename": filename,
        "url": f"/api/v1/uploads/cover/{filename}"
    }

async def save_image_from_bytes(img_bytes: bytes) -> str:
    try:
        img = Image.open(io.BytesIO(img_bytes))
        img_format = img.format.lower() if img.format else "jpeg"
        if img_format == "jpeg":
            ext = ".jpg"
        elif img_format == "png":
            ext = ".png"
        elif img_format == "webp":
            ext = ".webp"
        else:
            ext = ".jpg"
    except Exception:
        raise HTTPException(status_code=400, detail="Arquivo baixado não é uma imagem válida.")

    filename = f"{uuid.uuid4()}{ext}"
    destination = settings.COVERS_DIR / filename
    with open(destination, "wb") as f:
        f.write(img_bytes)
    return filename

@router.post("/cover-url")
async def download_cover_from_url(payload: CoverUrlRequest):
    url = payload.url.strip()
    if not url.startswith("http://") and not url.startswith("https://"):
        raise HTTPException(status_code=400, detail="URL inválida. Deve começar com http:// ou https://")

    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            resp = await client.get(url, headers=headers)
            if resp.status_code != 200:
                raise HTTPException(status_code=400, detail=f"Falha ao baixar imagem (HTTP {resp.status_code})")

            filename = await save_image_from_bytes(resp.content)
            return {
                "filename": filename,
                "url": f"/api/v1/uploads/cover/{filename}"
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao baixar imagem: {str(e)}")

@router.post("/auto-cover")
async def auto_search_cover(payload: AutoCoverRequest):
    title = payload.title.strip()
    if not title:
        raise HTTPException(status_code=400, detail="Título do jogo não pode ser vazio.")

    api_key = payload.api_key or settings.STEAMGRIDDB_API_KEY
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

    async with httpx.AsyncClient(timeout=12.0, follow_redirects=True) as client:
        # --- 1. TENTATIVA: SteamGridDB (Se tiver chave API configurada) ---
        if api_key:
            try:
                sgdb_headers = {"Authorization": f"Bearer {api_key}"}
                encoded_title = urllib.parse.quote(title)
                search_url = f"https://www.steamgriddb.com/api/v2/search/autocomplete/{encoded_title}"
                search_res = await client.get(search_url, headers=sgdb_headers)
                if search_res.status_code == 200:
                    data = search_res.json().get("data", [])
                    if data:
                        game_id = data[0].get("id")
                        # Buscar grids horizontais ou gerais
                        grids_url = f"https://www.steamgriddb.com/api/v2/grids/game/{game_id}?dimensions=600x900,920x430,460x215"
                        grids_res = await client.get(grids_url, headers=sgdb_headers)
                        if grids_res.status_code == 200:
                            grids = grids_res.json().get("data", [])
                            if grids:
                                img_url = grids[0].get("url")
                                img_resp = await client.get(img_url, headers=headers)
                                if img_resp.status_code == 200:
                                    filename = await save_image_from_bytes(img_resp.content)
                                    return {
                                        "filename": filename,
                                        "url": f"/api/v1/uploads/cover/{filename}",
                                        "source": "SteamGridDB"
                                    }
            except Exception as e:
                print("SteamGridDB search failed, falling back to Steam Store:", e)

        # --- 2. TENTATIVA: Steam Store Public Search (Sem chave, oficial) ---
        try:
            encoded_title = urllib.parse.quote(title)
            steam_search_url = f"https://store.steampowered.com/api/storesearch/?term={encoded_title}&l=portuguese&cc=BR"
            resp = await client.get(steam_search_url, headers=headers)
            if resp.status_code == 200:
                items = resp.json().get("items", [])
                if items:
                    app_id = items[0].get("id")
                    # Tentar capa em alta resolução library_600x900 ou header
                    candidate_urls = [
                        f"https://shared.cloudflare.steamstatic.com/store_item_assets/steam/apps/{app_id}/header.jpg",
                        f"https://cdn.akamai.steamstatic.com/steam/apps/{app_id}/header.jpg",
                        items[0].get("tiny_image", "")
                    ]
                    for img_url in candidate_urls:
                        if not img_url:
                            continue
                        img_resp = await client.get(img_url, headers=headers)
                        if img_resp.status_code == 200 and len(img_resp.content) > 1000:
                            filename = await save_image_from_bytes(img_resp.content)
                            return {
                                "filename": filename,
                                "url": f"/api/v1/uploads/cover/{filename}",
                                "source": "Steam Store"
                            }
        except Exception as e:
            print("Steam Store search failed:", e)

        # --- 3. TENTATIVA: RAWG Open Game Search (Sem chave ou fallback público) ---
        try:
            # Busca de imagem pública via DuckDuckGo imagens limpa
            ddg_url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(title + ' game cover horizontal')}"
            ddg_resp = await client.get(ddg_url, headers=headers)
            # Se não encontrar, levanta 404
        except Exception:
            pass

    raise HTTPException(
        status_code=404,
        detail=f"Não foi possível encontrar automaticamente uma capa para '{title}'. Tente inserir o link da imagem."
    )

@router.get("/cover/{filename}")
def get_cover(filename: str):
    file_path = settings.COVERS_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Imagem não encontrada")
    return FileResponse(file_path)
