import uuid
import io
import httpx
from pathlib import Path
from pydantic import BaseModel, HttpUrl
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from PIL import Image
from backend.app.core.config import settings

router = APIRouter()

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}

class CoverUrlRequest(BaseModel):
    url: str

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

            img_bytes = resp.content
            # Validar formato com Pillow
            try:
                img = Image.open(io.BytesIO(img_bytes))
                img_format = img.format.lower()
                if img_format == "jpeg":
                    ext = ".jpg"
                elif img_format == "png":
                    ext = ".png"
                elif img_format == "webp":
                    ext = ".webp"
                else:
                    ext = ".jpg"
            except Exception:
                raise HTTPException(status_code=400, detail="O link fornecido não contém uma imagem válida.")

            filename = f"{uuid.uuid4()}{ext}"
            destination = settings.COVERS_DIR / filename

            with open(destination, "wb") as f:
                f.write(img_bytes)

            return {
                "filename": filename,
                "url": f"/api/v1/uploads/cover/{filename}"
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao baixar imagem: {str(e)}")

@router.get("/cover/{filename}")
def get_cover(filename: str):
    file_path = settings.COVERS_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Imagem não encontrada")
    return FileResponse(file_path)
