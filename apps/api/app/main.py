from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.database import Base, engine
from app.core.settings import settings
from app.routers import activity, auth, books, recommend, search

app = FastAPI(title=settings.app_name)

origins = [o.strip() for o in str(getattr(settings, "web_origins", "http://localhost:3000")).split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Base.metadata.create_all(bind=engine)

app.include_router(auth.router, prefix=settings.api_prefix)
app.include_router(books.router, prefix=settings.api_prefix)
app.include_router(search.router, prefix=settings.api_prefix)
app.include_router(recommend.router, prefix=settings.api_prefix)
app.include_router(activity.router, prefix=settings.api_prefix)


@app.get("/health")
def health():
    return {"ok": True}
