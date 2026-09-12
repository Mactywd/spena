from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.security import SESSION_COOKIE, issue_session_cookie, verify_password

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class LoginRequest(BaseModel):
    password: str


@router.post("/login", status_code=status.HTTP_204_NO_CONTENT)
async def login(payload: LoginRequest, response: Response) -> Response:
    configured = get_settings().app_password_hash
    if not configured or not verify_password(payload.password, configured):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "password errata")
    issue_session_cookie(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response) -> Response:
    # Fuori dal gate di proposito: cancella solo un cookie nel browser di chi chiama,
    # non legge né scrive dati applicativi. Metterla dietro require_session creerebbe
    # un vicolo cieco per chi ha un cookie scaduto o manomesso.
    response.delete_cookie(SESSION_COOKIE)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response
