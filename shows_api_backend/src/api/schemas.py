from __future__ import annotations

import datetime as dt
from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field, PositiveInt, field_validator


class ORMBase(BaseModel):
    """
    Base model enabling Pydantic v2 from_attributes (replacement for orm_mode).
    """

    model_config = {"from_attributes": True}


# PUBLIC_INTERFACE
class UserCreate(BaseModel):
    """Payload for creating a user account."""
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=8, max_length=128, description="Plain password to hash")
    display_name: Optional[str] = Field(None, max_length=120, description="Displayed name")

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """Basic password validation; ensure minimum length."""
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        return v


# PUBLIC_INTERFACE
class UserRead(ORMBase):
    """User record returned to clients."""
    id: int
    email: EmailStr
    display_name: Optional[str]
    is_active: bool
    created_at: dt.datetime
    updated_at: dt.datetime


# PUBLIC_INTERFACE
class TrackRead(ORMBase):
    """Track information for a show."""
    id: int
    title: str
    position: PositiveInt


# PUBLIC_INTERFACE
class ShowCreate(BaseModel):
    """Payload for creating a show."""
    date: dt.date = Field(..., description="Show date")
    location: str = Field(..., min_length=2, max_length=255, description="City, State or similar")
    venue: str = Field(..., min_length=1, max_length=255)
    notes: Optional[str] = Field(None, max_length=2000)


# PUBLIC_INTERFACE
class ShowRead(ORMBase):
    """Show information returned to clients."""
    id: int
    date: dt.date
    location: str
    venue: str
    notes: Optional[str]
    tracks: List[TrackRead] = Field(default_factory=list)


# PUBLIC_INTERFACE
class TrackCreate(BaseModel):
    """Payload to add a track to a show."""
    show_id: int
    title: str = Field(..., min_length=1, max_length=255)
    position: PositiveInt


# PUBLIC_INTERFACE
class FavoriteCreate(BaseModel):
    """Payload to favorite a show for a user."""
    user_id: int
    show_id: int


# PUBLIC_INTERFACE
class FavoriteRead(ORMBase):
    """Favorite relation returned to clients."""
    id: int
    user_id: int
    show_id: int
    created_at: dt.datetime
