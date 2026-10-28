"""A paused public-page check the operator can solve in the chat."""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.models.user import User
from app.services.auth import get_current_user
from app.services import web_research

router = APIRouter(prefix="/research", tags=["research"])


class Point(BaseModel):
    x: float = Field(ge=0, le=2000)
    y: float = Field(ge=0, le=2000)


class Keys(BaseModel):
    text: str = Field(max_length=200)


@router.get("/challenges")
async def list_challenges(_user: User = Depends(get_current_user)) -> list[dict]:
    return web_research.challenges()


@router.get("/challenges/{challenge_id}/shot")
async def shot(challenge_id: str, _user: User = Depends(get_current_user)) -> Response:
    image = web_research.challenge_shot(challenge_id)
    if not image:
        raise HTTPException(404, "Снимок ещё не готов")
    return Response(content=image, media_type="image/jpeg", headers={"Cache-Control": "no-store"})


@router.post("/challenges/{challenge_id}/click")
async def click(challenge_id: str, body: Point, _user: User = Depends(get_current_user)) -> dict:
    if not await web_research.challenge_click(challenge_id, body.x, body.y):
        raise HTTPException(409, "Страницу сейчас нельзя нажать")
    return {"ok": True}


@router.post("/challenges/{challenge_id}/type")
async def type_text(challenge_id: str, body: Keys, _user: User = Depends(get_current_user)) -> dict:
    if not await web_research.challenge_type(challenge_id, body.text):
        raise HTTPException(409, "Поле сейчас нельзя заполнить")
    return {"ok": True}


@router.post("/challenges/{challenge_id}/finish")
async def finish(challenge_id: str, _user: User = Depends(get_current_user)) -> dict:
    return {"ok": await web_research.challenge_finish(challenge_id)}


@router.post("/challenges/{challenge_id}/skip")
async def skip(challenge_id: str, _user: User = Depends(get_current_user)) -> dict:
    if not web_research.challenge_skip(challenge_id):
        raise HTTPException(404, "Проверка уже закрыта")
    return {"ok": True}
