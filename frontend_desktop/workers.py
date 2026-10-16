"""Execução de chamadas de rede fora da thread da UI."""
import logging
from typing import Any, Callable

from PySide6.QtCore import QThread, Signal

logger = logging.getLogger(__name__)


class ApiWorker(QThread):
    """Executa `func(*args, **kwargs)` em background e emite `succeeded(result)` ou `failed(msg)`."""
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, func: Callable[..., Any], *args, parent=None, **kwargs):
        super().__init__(parent)
        self._func, self._args, self._kwargs = func, args, kwargs

    def run(self):
        try:
            self.succeeded.emit(self._func(*self._args, **self._kwargs))
        except Exception as e:
            logger.warning("Falha em chamada de API em background: %s", e)
            self.failed.emit(str(e))


def run_async(owner, func, on_success, on_error=None, *args, **kwargs) -> ApiWorker:
    """Dispara o worker e o mantém referenciado em `owner._workers` até terminar."""
    worker = ApiWorker(func, *args, parent=owner, **kwargs)
    workers = owner.__dict__.setdefault("_workers", set())
    workers.add(worker)
    worker.succeeded.connect(on_success)
    if on_error:
        worker.failed.connect(on_error)
    worker.finished.connect(lambda: workers.discard(worker))
    worker.start()
    return worker
