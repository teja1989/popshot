from fastapi import APIRouter
from pydantic import BaseModel

from popshot_api.auth.dependencies import CurrentIdentity

router = APIRouter(prefix="/v1")


class Me(BaseModel):
    email: str
    display_name: str | None
    picture_url: str | None


@router.get("/me")
def me(identity: CurrentIdentity) -> Me:
    return Me(
        email=identity.email,
        display_name=identity.display_name,
        picture_url=identity.picture_url,
    )
