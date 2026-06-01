from typing import Literal

from pydantic import BaseModel, Field


class Token(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = Field(default="bearer")


class TokenPayload(BaseModel):
    sub: str | None = None
