from pydantic import BaseModel, EmailStr, Field


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ActivityIn(BaseModel):
    book_id: int
    event_type: str = Field(pattern="^(read|liked|dismissed|viewed)$")
    dwell_ms: int = 0


class BookOut(BaseModel):
    book_id: int
    title: str | None = None
    author: str | None = None
    year: int | None = None
    avg_rating: float | None = None
    rating_count: int | None = None
    image_url_m: str | None = None


class RecommendOut(BaseModel):
    book: BookOut
    score: float
    reasons: list[str]
    badges: list[str]


class RecommendResponse(BaseModel):
    items: list[RecommendOut]


class BookListResponse(BaseModel):
    items: list[BookOut]
    page: int
    limit: int


class MeOut(BaseModel):
    id: int
    email: EmailStr
    role: str


class InteractionOut(BaseModel):
    interaction_id: int
    ok: bool = True


class SimilarResponse(BaseModel):
    items: list[RecommendOut]


class ProfileOut(BaseModel):
    genres: list[str] = []
    moods: list[str] = []
    length: str = "any"
    readIds: list[int] = []
    lovedIds: list[int] = []
    onboarded: bool = False


class ProfileUpdateIn(BaseModel):
    genres: list[str] = []
    moods: list[str] = []
    length: str = "any"
    readIds: list[int] = []
    lovedIds: list[int] = []
    onboarded: bool = False


class SearchResponse(BaseModel):
    items: list[BookOut]


class LegacyRecommendOut(BaseModel):
    book_id: int
    score: float
    reason: str
