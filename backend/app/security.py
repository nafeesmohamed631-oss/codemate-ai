from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from pwdlib import PasswordHash
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from .config import settings
from .database import get_db
from .models import User

ph = PasswordHash.recommended()
bearer = HTTPBearer()

def hash_password(p): return ph.hash(p)
def verify_password(p, h): return ph.verify(p, h)

def token(user_id):
    exp = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    return jwt.encode({"sub": str(user_id), "exp": exp}, settings.jwt_secret, algorithm="HS256")

def current_user(c: HTTPAuthorizationCredentials = Depends(bearer), db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(c.credentials, settings.jwt_secret, algorithms=["HS256"])
        uid = int(payload["sub"])
    except (JWTError, ValueError, KeyError):
        raise HTTPException(401, "Invalid token")
    user = db.get(User, uid)
    if not user: raise HTTPException(401, "User not found")
    return user
