from pathlib import Path
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str = "sqlite:///./codemate.db"
    jwt_secret: str = "change-this-in-production"
    jwt_expire_minutes: int = 43200
    upload_dir: str = "./storage"
    max_file_mb: int = 25
    llm_provider: str = "auto"
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = "gemini-2.5-flash"

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()

def save_llm_settings(provider: str = None, api_key: str = None, model: str = None, base_url: str = None):
    """Update settings in memory and persist them to backend/.env"""
    if provider is not None:
        settings.llm_provider = provider
    if api_key is not None:
        settings.llm_api_key = api_key.strip()
    if model is not None:
        settings.llm_model = model.strip()
    if base_url is not None:
        settings.llm_base_url = base_url.strip()

    # Determine default model if blank or mismatch
    if settings.llm_provider == "gemini" and (not settings.llm_model or "gpt" in settings.llm_model.lower()):
        settings.llm_model = "gemini-2.5-flash"
    elif settings.llm_provider == "openai" and (not settings.llm_model or "gemini" in settings.llm_model.lower()):
        settings.llm_model = "gpt-4o-mini"

    # Persist to .env file
    env_path = Path(".env")
    env_lines = []
    keys_written = set()

    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line_strip = line.strip()
            if not line_strip or line_strip.startswith("#") or "=" not in line_strip:
                env_lines.append(line)
                continue
            k, _ = line_strip.split("=", 1)
            k = k.strip()
            if k == "LLM_PROVIDER":
                env_lines.append(f"LLM_PROVIDER={settings.llm_provider}")
                keys_written.add("LLM_PROVIDER")
            elif k == "LLM_API_KEY":
                env_lines.append(f"LLM_API_KEY={settings.llm_api_key}")
                keys_written.add("LLM_API_KEY")
            elif k == "LLM_MODEL":
                env_lines.append(f"LLM_MODEL={settings.llm_model}")
                keys_written.add("LLM_MODEL")
            elif k == "LLM_BASE_URL":
                env_lines.append(f"LLM_BASE_URL={settings.llm_base_url}")
                keys_written.add("LLM_BASE_URL")
            else:
                env_lines.append(line)

    if "LLM_PROVIDER" not in keys_written:
        env_lines.append(f"LLM_PROVIDER={settings.llm_provider}")
    if "LLM_API_KEY" not in keys_written:
        env_lines.append(f"LLM_API_KEY={settings.llm_api_key}")
    if "LLM_MODEL" not in keys_written:
        env_lines.append(f"LLM_MODEL={settings.llm_model}")
    if "LLM_BASE_URL" not in keys_written:
        env_lines.append(f"LLM_BASE_URL={settings.llm_base_url}")

    env_path.write_text("\n".join(env_lines) + "\n", encoding="utf-8")

