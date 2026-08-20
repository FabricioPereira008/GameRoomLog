import uuid
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from backend.app.core.config import settings

router = APIRouter()

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}

@router.post("/cover")
async def upload_cover(file: UploadFile = File(...)):
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Formato de imagem inválido. Suportados: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    # Gera nome único para o arquivo
    filename = f"{uuid.uuid4()}{ext}"
    destination = settings.COVERS_DIR / filename

    content = await file.read()
    with open(destination, "wb") as f:
        f.write(content)

    return {
        "filename": filename,
        "url": f"/api/v1/uploads/cover/{filename}"
    }

@router.get("/cover/{filename}")
def get_cover(filename: str):
    file_path = settings.COVERS_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Imagem não encontrada")
    return FileResponse(file_path)
