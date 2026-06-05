from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path

class Settings(BaseSettings):
    # DIR
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
    DATABASE_DIR: Path = BASE_DIR / "database"
    # SQL
    SQLITE_PATH: Path = DATABASE_DIR / "db"
    CHROMA_PATH: Path = DATABASE_DIR / "chroma"
    # VDB
    CHROMA_COLLECTION: str = "claims_embeddings"
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    #Threshold
    SIMILARITY_THRESHOLD: float = 0.85
    CONFIDENCE_THRESHOLD_INSERT: float = 0.80
    #Load enviornment variables & crash handeling
    GOOGLE_API_KEY: str
    TAVILY_API_KEY: str
    model_config = SettingsConfigDict(env_file=Path(__file__).resolve().parent.parent.parent /".env", env_file_encoding="utf-8",extra="ignore")

settings = Settings()