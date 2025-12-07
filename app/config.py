import hmac
import hashlib
from pydantic_settings import BaseSettings
from pydantic import Field, ConfigDict

class Settings(BaseSettings):
    model_config = ConfigDict(env_file=".env", extra="ignore")
    
    DATABASE_URL: str
    WEBHOOK_SECRET: str
    LOG_LEVEL: str = "INFO"

settings = Settings()

def verify_signature(secret:str,raw_body:bytes,header_signature:str | None)->bool:

    if not secret:
        return False
    if not header_signature:
        return False
    
    computed = hmac.new(
        key = secret.encode("utf-8"),
        msg=raw_body,
        digestmod=hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(computed,header_signature)
    