from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="YOUFY_", env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://youfy:youfy@localhost:5433/youfy"
    data_dir: Path = Path("./data")
    fma_dump_dir: Path = Path("./data/raw/fma")
