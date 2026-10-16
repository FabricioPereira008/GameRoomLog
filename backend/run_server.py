import os
import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "backend.app.main:app",
        host=os.environ.get("GAMEROOM_HOST", "127.0.0.1"),
        port=int(os.environ.get("GAMEROOM_PORT", "8000")),
        reload=os.environ.get("GAMEROOM_RELOAD", "1") == "1",
    )
