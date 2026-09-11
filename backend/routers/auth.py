"""
Authentication routes: register, login, me.

Login uses OAuth2PasswordRequestForm (standard username/password form
fields) rather than a JSON body - this is what lets Swagger UI's
"Authorize" button obtain and attach a Bearer token automatically for
testing the rest of the API.
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr, Field

from backend.core.security import get_current_user
from backend.services import auth_service
from backend.services.auth_service import DuplicateUserError
from backend.services.notification_service import notify
from backend.utils.jwt import create_access_token

router = APIRouter(prefix="/auth", tags=["Authentication"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class UserRegister(BaseModel):
    username: str = Field(
        ..., min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_]+$"
    )
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=128)


class UserPublic(BaseModel):
    id: int
    username: str
    email: str
    role: str
    created_at: datetime
    updated_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post(
    "/register",
    response_model=UserPublic,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
)
def register(payload: UserRegister):
    try:
        user = auth_service.create_user(
            username=payload.username,
            email=payload.email,
            password=payload.password,
        )
    except DuplicateUserError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username or email is already registered",
        )
    notify(user["id"], user["username"], "REGISTER", details=f"email={user['email']}")
    return user


@router.post("/login", response_model=TokenResponse, summary="Log in and get a JWT")
def login(request: Request, form_data: OAuth2PasswordRequestForm = Depends()):
    client_ip = request.client.host if request.client else None
    user = auth_service.authenticate_user(form_data.username, form_data.password)

    if not user:
        # Log the failed attempt. If the username doesn't exist at all,
        # user_id is logged as NULL rather than leaking existence via
        # a different error path.
        existing = auth_service.get_user_by_username(form_data.username)
        auth_service.record_login_log(
            user_id=existing["id"] if existing else None,
            ip_address=client_ip,
            status="failed",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    auth_service.record_login_log(
        user_id=user["id"], ip_address=client_ip, status="success"
    )
    notify(user["id"], user["username"], "LOGIN", details=f"ip={client_ip}")

    access_token = create_access_token(
        {
            "user_id": user["id"],
            "username": user["username"],
            "role": user["role"],
        }
    )
    return TokenResponse(access_token=access_token)


@router.get("/me", response_model=UserPublic, summary="Get the current logged-in user")
def read_current_user(current_user: dict = Depends(get_current_user)):
    user = auth_service.get_user_by_id(current_user["user_id"])
    if not user:
        # Token was valid but the user no longer exists in the DB.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    return user
