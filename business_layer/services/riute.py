from typing import AsyncIterable

from fastapi import FastAPI, APIRouter, WebSocket
from fastapi.sse import EventSourceResponse, ServerSentEvent
from pydantic import BaseModel

router = APIRouter(
    prefix="/riute",
)


class CodeRequest(BaseModel):
    code: str

