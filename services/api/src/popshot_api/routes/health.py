from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class Health(BaseModel):
    status: Literal["ok"] = "ok"


@router.get("/healthz", include_in_schema=False)
async def healthz() -> Health:
    """Liveness only. It doesn't touch the database, so a DB blip won't restart instances."""
    return Health()
