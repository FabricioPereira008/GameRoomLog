"""Contrato dos provedores de biblioteca de lojas (Steam, Heroic...)."""
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Protocol


class LibraryProviderError(Exception):
    """Falha esperada de um provedor (key inválida, perfil privado, arquivo ausente).

    A mensagem é exibida ao usuário; nunca inclua segredos nela.
    """


@dataclass(frozen=True)
class LibraryEntry:
    store: str
    external_id: str
    title: str
    played_hours: Optional[float] = None
    is_game: bool = True  # False para DLC, ferramentas, trilhas etc. identificados pelo provedor
    developer: Optional[str] = None  # como a loja informa (pode vir com sufixo jurídico)


class LibraryProvider(Protocol):
    store: str

    def fetch(self) -> List[LibraryEntry]:
        """Lê a biblioteca da loja. Levanta LibraryProviderError em falhas esperadas."""
        ...


# store -> fábrica do provedor (instanciado a cada scan, para ler a configuração atual)
PROVIDERS: Dict[str, Callable[[], LibraryProvider]] = {}


def register_provider(store: str, factory: Callable[[], LibraryProvider]) -> None:
    PROVIDERS[store] = factory
