"""Profile: app-owned preferences over platform-owned identity."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ..core.dependencies import current_principal, profile_service
from ..schemas import ErrorResponse, ProfilePatch, ProfileResponse
from ..security import Principal
from ..services.profile_service import HandleTaken, InvalidPreference, ProfileService

router = APIRouter(prefix="/api/v1", tags=["profile"])


def _err(status: int, code: str, message: str, **details) -> HTTPException:
    return HTTPException(status_code=status,
                         detail={"error": {"code": code, "message": message, "details": details}})


@router.get("/me", response_model=ProfileResponse, summary="Current user's profile")
def get_me(
    principal: Principal = Depends(current_principal),
    svc: ProfileService = Depends(profile_service),
) -> ProfileResponse:
    return ProfileResponse(**svc.view(principal).__dict__)


@router.patch(
    "/me",
    response_model=ProfileResponse,
    summary="Update app-owned preferences",
    responses={409: {"model": ErrorResponse}, 400: {"model": ErrorResponse}},
)
def patch_me(
    patch: ProfilePatch,
    principal: Principal = Depends(current_principal),
    svc: ProfileService = Depends(profile_service),
) -> ProfileResponse:
    try:
        # exclude_unset so an omitted field is left alone rather than nulled.
        view = svc.update(principal, patch.model_dump(exclude_unset=True))
    except HandleTaken as exc:
        raise _err(409, "handle_taken", "That handle is already in use", handle=str(exc))
    except InvalidPreference as exc:
        raise _err(400, "invalid_preference", str(exc), field=exc.field)
    return ProfileResponse(**view.__dict__)
