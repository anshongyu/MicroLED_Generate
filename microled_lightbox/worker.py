"""Thread-confined Speos generation worker."""

from threading import Event

from PySide6.QtCore import QObject, Signal, Slot

from microled_lightbox.models import GenerationConfig
from microled_lightbox.speos_gateway import (
    GenerationCancelled,
    GenerationProgress,
    SpeosGateway,
)


class GenerationWorker(QObject):
    progress = Signal(object)
    succeeded = Signal(str)
    failed = Signal(str)
    cancelled = Signal()
    finished = Signal()

    def __init__(self, config: GenerationConfig) -> None:
        super().__init__()
        self._config = config
        self._cancel_event = Event()

    @Slot()
    def run(self) -> None:
        try:
            output_path = SpeosGateway().generate(
                self._config,
                progress=self._emit_progress,
                is_cancelled=self._cancel_event.is_set,
            )
        except GenerationCancelled:
            self.cancelled.emit()
        except Exception as error:
            self.failed.emit(f"{type(error).__name__}: {error}")
        else:
            self.succeeded.emit(str(output_path))
        finally:
            self.finished.emit()

    def cancel(self) -> None:
        self._cancel_event.set()

    def _emit_progress(self, update: GenerationProgress) -> None:
        self.progress.emit(update)
