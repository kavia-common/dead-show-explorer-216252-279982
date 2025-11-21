import hashlib
import hmac
import logging
from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from src.api.repositories import FavoriteRepository, ShowRepository, TrackRepository, UserRepository
from src.api.schemas import (
    FavoriteCreate,
    FavoriteRead,
    ShowCreate,
    ShowRead,
    TrackCreate,
    TrackRead,
    UserCreate,
    UserRead,
)

logger = logging.getLogger(__name__)


def _hash_password(secret: str, salt: str) -> str:
    """
    Derive a salted password hash using SHA-256 HMAC.
    In production consider using argon2/bcrypt via passlib; we keep stdlib here for simplicity.
    """
    digest = hmac.new(salt.encode("utf-8"), secret.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{salt}${digest}"


def _verify_password(secret: str, hashed: str) -> bool:
    try:
        salt, digest = hashed.split("$", 1)
    except ValueError:
        return False
    expected = hmac.new(salt.encode("utf-8"), secret.encode("utf-8"), hashlib.sha256).hexdigest()
    return hmac.compare_digest(digest, expected)


class UserService:
    """Business logic for users."""

    def __init__(self, session: AsyncSession, password_salt: str = "gd-salt") -> None:
        self.session = session
        self.users = UserRepository(session)
        self.password_salt = password_salt

    # PUBLIC_INTERFACE
    async def register(self, payload: UserCreate) -> UserRead:
        """Create a new user with a salted password hash."""
        password_hash = _hash_password(payload.password, self.password_salt)
        user = await self.users.create(email=str(payload.email), password_hash=password_hash, display_name=payload.display_name)
        await self.session.commit()
        return UserRead.model_validate(user)

    # PUBLIC_INTERFACE
    async def authenticate(self, email: str, password: str) -> Optional[UserRead]:
        """Validate credentials and return user if valid."""
        user = await self.users.get_by_email(email)
        if not user:
            return None
        if not _verify_password(password, user.password_hash):
            return None
        return UserRead.model_validate(user)


class ShowService:
    """Business logic for shows and tracks."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.shows = ShowRepository(session)
        self.tracks = TrackRepository(session)

    # PUBLIC_INTERFACE
    async def create_show(self, payload: ShowCreate) -> ShowRead:
        """Create a new show with optional notes."""
        show = await self.shows.create(date=payload.date, location=payload.location, venue=payload.venue, notes=payload.notes)
        await self.session.commit()
        # Reload tracks list empty
        return ShowRead.model_validate(show)

    # PUBLIC_INTERFACE
    async def add_track(self, payload: TrackCreate) -> TrackRead:
        """Add a track to a show enforcing unique position per show."""
        track = await self.tracks.add_track(show_id=payload.show_id, title=payload.title, position=payload.position)
        await self.session.commit()
        return TrackRead.model_validate(track)

    # PUBLIC_INTERFACE
    async def get_show(self, show_id: int) -> Optional[ShowRead]:
        """Fetch show by id."""
        show = await self.shows.get(show_id)
        if not show:
            return None
        # Optionally could prefetch tracks
        return ShowRead.model_validate(show)

    # PUBLIC_INTERFACE
    async def search(self, *, date: Optional[str] = None, location: Optional[str] = None, venue: Optional[str] = None, limit: int = 50, offset: int = 0) -> List[ShowRead]:
        """Search shows by optional filters."""
        items = await self.shows.search(date=date, location=location, venue=venue, limit=limit, offset=offset)
        return [ShowRead.model_validate(x) for x in items]


class FavoriteService:
    """Business logic for favorites."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.favorites = FavoriteRepository(session)

    # PUBLIC_INTERFACE
    async def add_favorite(self, payload: FavoriteCreate) -> FavoriteRead:
        """Add a show to user's favorites."""
        fav = await self.favorites.add(user_id=payload.user_id, show_id=payload.show_id)
        await self.session.commit()
        return FavoriteRead.model_validate(fav)

    # PUBLIC_INTERFACE
    async def remove_favorite(self, user_id: int, show_id: int) -> bool:
        """Remove a favorite; returns True if removed."""
        ok = await self.favorites.remove(user_id=user_id, show_id=show_id)
        await self.session.commit()
        return ok

    # PUBLIC_INTERFACE
    async def list_user_favorites(self, user_id: int) -> List[FavoriteRead]:
        """List favorites for a user."""
        items = await self.favorites.list_for_user(user_id=user_id)
        return [FavoriteRead.model_validate(x) for x in items]
