from pathlib import Path
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(ROOT_DIR / ".env")


class Settings(BaseSettings):
    GROQ_API_KEY: str = ""
    LLM_MODEL: str = "llama-3.3-70b-versatile"
    LLM_BASE_URL: str = "https://api.groq.com/openai/v1"
    DATABASE_URL: str = "sqlite:///./hospital.db"

    GMAIL_SENDER_EMAIL: str = ""
    GMAIL_APP_PASSWORD: str = ""
    OPERATOR_NOTIFICATION_EMAIL: str = ""

    CONFIG_DIR: Path = Path(__file__).resolve().parent
    SAFETY_RULES_PATH: Path = CONFIG_DIR / "safety_rules.yaml"
    DEPARTMENTS_PATH: Path = CONFIG_DIR / "departments.yaml"

    model_config = SettingsConfigDict(
        env_file=str(ROOT_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()