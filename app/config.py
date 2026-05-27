from dataclasses import dataclass
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    storage_root: Path = Path(os.getenv("STORAGE_ROOT", "/storage"))
    max_upload_size_bytes: int = int(os.getenv("MAX_UPLOAD_SIZE_BYTES", str(10 * 1024 * 1024)))

    @property
    def upload_dir(self) -> Path:
        return self.storage_root / "uploads"


settings = Settings()
