from typing import Optional

from pydantic import BaseModel


class Tag(BaseModel):
    current_time: Optional[int] = None
    user_id: Optional[str] = None

    class Config:
        arbitrary_types_allowed = True
