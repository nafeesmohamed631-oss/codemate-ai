from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str = "sqlite:///./codemate.db"
    jwt_secret: str = "change-this-in-production"
    jwt_expire_minutes: int = 43200
    upload_dir: str = "./storage"
    max_file_mb: int = 25
    llm_base_url: str = "https://api.openai.com/v1"
    llm_api_key: str = ""
    llm_model: str = "gpt-4.1-mini"
    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
