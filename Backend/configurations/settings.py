from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path

class Settings(BaseSettings):
    # DIR path
    BASE_DIR: Path = Path(__file__).resolve().parent.parent
    DATABASE_DIR: Path = BASE_DIR / "Database"
    # SQL path
    SQLITE_PATH: Path = DATABASE_DIR / "db"
    CHROMA_PATH: Path = DATABASE_DIR / "chroma"
    # VDB path
    CHROMA_COLLECTION: str = "claims_embeddings"
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    #Threshold
    SIMILARITY_THRESHOLD: float = 0.85 # this threshold values were standard used everywhere in youtube also
    CONFIDENCE_THRESHOLD_INSERT: float = 0.75
    #Load enviornment variables
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

settings = Settings()