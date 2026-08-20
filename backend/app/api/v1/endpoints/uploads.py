import uuid
import io
import urllib.parse
import httpx
from pathlib import Path
from typing import Optional
from pydantic import BaseModel
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from PIL import Image, ImageFilter
from backend.app.core.config import settings
from backend.app.core.database import get_db
from backend.app.models.game import Game

router = APIRouter()


ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}

class CoverUrlRequest(BaseModel):
    url: str

class AutoCoverRequest(BaseModel):
    title: str
    api_key: Optional[str] = None

def process_cover_image(img_bytes: bytes) -> tuple[bytes, str]:
    """Processa a imagem baixada para garantir que se encaixe perfeitamente no padrão vertical 600x900."""
    try:
        img = Image.open(io.BytesIO(img_bytes))
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGBA")
        else:
            img = img.convert("RGB")

        w, h = img.size
        current_ratio = w / h  # 600x900 -> 0.6667

        # Se já estiver em formato retrato proporcional (ex: 0.55 a 0.78), mantém o original
        if 0.55 <= current_ratio <= 0.78:
            out_io = io.BytesIO()
            img.convert("RGB").save(out_io, format="JPEG", quality=92)
            return out_io.getvalue(), ".jpg"

        # Se a imagem for horizontal (ex: 460x215 do Steam Header), cria um poster 600x900 centralizado
        target_w, target_h = 600, 900
        
        # Fundo: versão borrada da própria arte
        bg = img.resize((target_w, target_h), Image.Resampling.BILINEAR)
        bg = bg.filter(ImageFilter.GaussianBlur(radius=25))
        # Escurece levemente o fundo para destacar o centro
        dark_overlay = Image.new("RGBA", (target_w, target_h), (0, 0, 0, 80))
        bg = Image.alpha_composite(bg.convert("RGBA"), dark_overlay)

        # Arte central: redimensiona mantendo a proporção exata
        fit_scale = target_w / w
        fit_w = target_w
        fit_h = int(h * fit_scale)
        if fit_h > target_h:
            fit_scale = target_h / h
            fit_h = target_h
            fit_w = int(w * fit_scale)

        fg = img.resize((fit_w, fit_h), Image.Resampling.LANCZOS)
        
        paste_x = (target_w - fit_w) // 2
        paste_y = (target_h - fit_h) // 2

        bg.paste(fg, (paste_x, paste_y), fg if fg.mode == "RGBA" else None)

        out_io = io.BytesIO()
        bg.convert("RGB").save(out_io, format="JPEG", quality=92)
        return out_io.getvalue(), ".jpg"
    except Exception as e:
        print("Erro ao processar imagem com Pillow:", e)
        return img_bytes, ".jpg"

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
    processed_bytes, ext = process_cover_image(img_bytes)
    filename = f"{uuid.uuid4()}{ext}"
    destination = settings.COVERS_DIR / filename
    with open(destination, "wb") as f:
        f.write(processed_bytes)
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
        # --- 1. TENTATIVA: SteamGridDB (Priorizando formato vertical 600x900) ---
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
                        # Buscar primeiro dimensões verticais 600x900
                        grids_url = f"https://www.steamgriddb.com/api/v2/grids/game/{game_id}?dimensions=600x900"
                        grids_res = await client.get(grids_url, headers=sgdb_headers)
                        if grids_res.status_code == 200 and grids_res.json().get("data"):
                            grids = grids_res.json().get("data")
                            img_url = grids[0].get("url")
                            img_resp = await client.get(img_url, headers=headers)
                            if img_resp.status_code == 200:
                                filename = await save_image_from_bytes(img_resp.content)
                                return {
                                    "filename": filename,
                                    "url": f"/api/v1/uploads/cover/{filename}",
                                    "source": "SteamGridDB (600x900)"
                                }
                        
                        # Fallback no SGDB para outras dimensões
                        grids_url_any = f"https://www.steamgriddb.com/api/v2/grids/game/{game_id}"
                        grids_res_any = await client.get(grids_url_any, headers=sgdb_headers)
                        if grids_res_any.status_code == 200 and grids_res_any.json().get("data"):
                            grids = grids_res_any.json().get("data")
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

        # --- 2. TENTATIVA: Steam Store Public Search (Priorizando library_600x900 vertical) ---
        try:
            encoded_title = urllib.parse.quote(title)
            steam_search_url = f"https://store.steampowered.com/api/storesearch/?term={encoded_title}&l=portuguese&cc=BR"
            resp = await client.get(steam_search_url, headers=headers)
            if resp.status_code == 200:
                items = resp.json().get("items", [])
                if items:
                    app_id = items[0].get("id")
                    candidate_urls = [
                        f"https://shared.cloudflare.steamstatic.com/store_item_assets/steam/apps/{app_id}/library_600x900_2x.jpg",
                        f"https://shared.cloudflare.steamstatic.com/store_item_assets/steam/apps/{app_id}/library_600x900.jpg",
                        f"https://steamcdn-a.akamaihd.net/steam/apps/{app_id}/library_600x900_2x.jpg",
                        f"https://steamcdn-a.akamaihd.net/steam/apps/{app_id}/library_600x900.jpg",
                        f"https://shared.cloudflare.steamstatic.com/store_item_assets/steam/apps/{app_id}/header.jpg",
                        f"https://cdn.akamai.steamstatic.com/steam/apps/{app_id}/header.jpg"
                    ]
                    for img_url in candidate_urls:
                        try:
                            img_resp = await client.get(img_url, headers=headers)
                            if img_resp.status_code == 200 and len(img_resp.content) > 1500:
                                filename = await save_image_from_bytes(img_resp.content)
                                return {
                                    "filename": filename,
                                    "url": f"/api/v1/uploads/cover/{filename}",
                                    "source": "Steam Store"
                                }
                        except Exception:
                            continue
        except Exception as e:
            print("Steam Store search failed:", e)

    raise HTTPException(
        status_code=404,
        detail=f"Não foi possível encontrar automaticamente uma capa para '{title}'. Tente inserir o link da imagem."
    )

@router.post("/auto-cover-game/{game_id}")
async def auto_cover_game(
    game_id: int,
    api_key: Optional[str] = None,
    db: Session = Depends(get_db)
):
    game = db.query(Game).filter(Game.id == game_id).first()
    if not game:
        raise HTTPException(status_code=404, detail="Jogo não encontrado")

    try:
        res = await auto_search_cover(AutoCoverRequest(title=game.title, api_key=api_key))
        filename = res["filename"]
        game.cover_image = filename
        db.commit()
        return {
            "success": True,
            "game_id": game_id,
            "title": game.title,
            "filename": filename,
            "source": res.get("source")
        }
    except HTTPException:
        return {
            "success": False,
            "game_id": game_id,
            "title": game.title,
            "error": "Capa não encontrada"
        }
    except Exception as e:
        return {
            "success": False,
            "game_id": game_id,
            "title": game.title,
            "error": str(e)
        }

@router.get("/cover/{filename}")
def get_cover(filename: str):
    file_path = settings.COVERS_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Imagem não encontrada")
    return FileResponse(file_path)

