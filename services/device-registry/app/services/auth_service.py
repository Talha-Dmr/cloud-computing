from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import jwt
from passlib.context import CryptContext
import structlog

from ..config import settings

logger = structlog.get_logger()

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class AuthService:
    def __init__(self, db: Session):
        self.db = db

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash"""
        return pwd_context.verify(plain_password, hashed_password)

    def get_password_hash(self, password: str) -> str:
        """Generate password hash"""
        return pwd_context.hash(password)

    def create_access_token(
        self,
        data: Dict[str, Any],
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """Create a JWT access token"""
        to_encode = data.copy()

        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(
                minutes=settings.jwt_access_token_expire_minutes
            )

        to_encode.update({"exp": expire, "iat": datetime.utcnow()})
        encoded_jwt = jwt.encode(
            to_encode,
            settings.jwt_secret_key,
            algorithm=settings.jwt_algorithm
        )

        return encoded_jwt

    def create_device_token(self, device_id: str) -> str:
        """Create a JWT token for device authentication"""
        data = {
            "sub": device_id,
            "type": "device",
            "scope": "device:auth"
        }

        expires_delta = timedelta(days=365)  # Device tokens last longer
        return self.create_access_token(data, expires_delta)

    def create_user_token(
        self,
        user_id: str,
        email: str,
        scopes: list = ["read", "write"]
    ) -> str:
        """Create a JWT token for user authentication"""
        data = {
            "sub": user_id,
            "email": email,
            "type": "user",
            "scope": " ".join(scopes)
        }

        return self.create_access_token(data)

    async def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify and decode JWT token"""
        try:
            payload = jwt.decode(
                token,
                settings.jwt_secret_key,
                algorithms=[settings.jwt_algorithm]
            )

            # Check if token has expired
            exp = payload.get("exp")
            if exp and datetime.utcnow() > datetime.fromtimestamp(exp):
                logger.warning("Token expired", token=token[:10] + "...")
                return None

            # Validate required fields
            if "sub" not in payload:
                logger.warning("Token missing subject", token=token[:10] + "...")
                return None

            logger.info(
                "Token verified successfully",
                subject=payload.get("sub"),
                token_type=payload.get("type")
            )

            return payload

        except jwt.ExpiredSignatureError:
            logger.warning("Token expired", token=token[:10] + "...")
            return None
        except jwt.JWTError as e:
            logger.error("JWT validation error", error=str(e))
            return None

    async def get_current_user(
        self,
        token: str,
        required_scope: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Get current user from token with optional scope validation"""
        payload = await self.verify_token(token)
        if not payload:
            return None

        # Check scope if required
        if required_scope:
            token_scopes = payload.get("scope", "").split()
            if required_scope not in token_scopes:
                logger.warning(
                    "Insufficient token scope",
                    required=required_scope,
                    provided=token_scopes
                )
                return None

        return payload

    def hash_api_key(self, api_key: str) -> str:
        """Hash an API key"""
        return self.get_password_hash(api_key)

    def verify_api_key(self, api_key: str, hashed_key: str) -> bool:
        """Verify an API key against its hash"""
        return self.verify_password(api_key, hashed_key)