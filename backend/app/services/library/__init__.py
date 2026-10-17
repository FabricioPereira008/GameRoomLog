from backend.app.services.library.base import (
    LibraryEntry,
    LibraryProvider,
    LibraryProviderError,
    PROVIDERS,
    register_provider,
)

__all__ = ["LibraryEntry", "LibraryProvider", "LibraryProviderError", "PROVIDERS", "register_provider"]


from backend.app.services.library.steam import SteamProvider  # noqa: E402

register_provider("steam", SteamProvider)
