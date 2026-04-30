"""
NovelNest — Flask Application

Survey-driven personalisation:
  - No numeric user IDs exposed.
  - New visitors complete a 3-step survey (name → genres → books read).
  - Session stores: username, genres, read_book_ids, survey_user_id (mapped
    to the closest matching real user in the ratings data for CF scoring).
"""

import os
from pathlib import Path
from urllib.parse import urlparse, quote, unquote

def _env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}

# Keep OAuth transport behavior configurable for EC2/http vs HTTPS setups.
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1" if _env_bool("OAUTHLIB_INSECURE_TRANSPORT", True) else "0"

from flask_dance.contrib.google import make_google_blueprint, google
import json
import random
import pandas as pd
import time
from datetime import timedelta
from collections import defaultdict, deque
from flask import (
    Flask, render_template, request, session,
    redirect, url_for, flash, jsonify
)
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import generate_password_hash, check_password_hash
from flask_mail import Mail, Message
import pyotp

from data_loader import DataLoader
from recommenders.hybrid import HybridRecommender
from aws.kinesis_producer import KinesisEventProducer

try:
    import boto3
except ImportError:
    boto3 = None

def send_otp_email(email, otp):
    print(f"\n📩 OTP for {email}: {otp}\n")


USERS_FILE = Path(__file__).resolve().parent / "users.json"
AUDIT_LOG_FILE = Path(__file__).resolve().parent / "audit_logs.json"
ACTIVITY_LOG_FILE = Path(__file__).resolve().parent / "activity_logs.json"
PUBLIC_SITE = "13.204.232.136:5000"


def _parse_s3_uri(uri: str) -> tuple[str, str]:
    parsed = urlparse(uri)
    if parsed.scheme != "s3" or not parsed.netloc:
        raise ValueError("S3 URI must look like s3://bucket/path/to/file.json")
    key = parsed.path.lstrip("/")
    if not key:
        raise ValueError("S3 URI must include an object key")
    return parsed.netloc, key


def _use_s3_users() -> bool:
    return os.environ.get("USER_STORE", "").strip().lower() == "s3"


def _s3_users_uri() -> str:
    return os.environ.get("S3_USERS_URI", "").strip()


def _load_users_from_local() -> list:
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _save_users_to_local(users: list) -> None:
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, indent=4)


def _load_users_from_s3() -> list:
    if boto3 is None:
        print("[WARN] USER_STORE=s3 but boto3 is not installed. Falling back to local users.json.")
        return _load_users_from_local()

    uri = _s3_users_uri()
    if not uri:
        print("[WARN] USER_STORE=s3 but S3_USERS_URI is missing. Falling back to local users.json.")
        return _load_users_from_local()

    try:
        bucket, key = _parse_s3_uri(uri)
        s3 = boto3.client("s3")
        obj = s3.get_object(Bucket=bucket, Key=key)
        payload = obj["Body"].read().decode("utf-8")
        return json.loads(payload)
    except Exception as exc:
        print(f"[WARN] Failed to read users from S3 ({uri}): {exc}. Falling back to local users.json.")
        return _load_users_from_local()


def _save_users_to_s3(users: list) -> bool:
    if boto3 is None:
        print("[WARN] USER_STORE=s3 but boto3 is not installed. Saving to local users.json.")
        _save_users_to_local(users)
        return False

    uri = _s3_users_uri()
    if not uri:
        print("[WARN] USER_STORE=s3 but S3_USERS_URI is missing. Saving to local users.json.")
        _save_users_to_local(users)
        return False

    try:
        bucket, key = _parse_s3_uri(uri)
        s3 = boto3.client("s3")
        body = json.dumps(users, indent=4).encode("utf-8")
        s3.put_object(
            Bucket=bucket,
            Key=key,
            Body=body,
            ContentType="application/json",
        )
        return True
    except Exception as exc:
        print(f"[WARN] Failed to write users to S3 ({uri}): {exc}. Saving to local users.json.")
        _save_users_to_local(users)
        return False


def _audit_log(event: str, email: str | None = None, status: str = "success", metadata: dict | None = None) -> None:
    entry = {
        "ts": int(time.time()),
        "event": event,
        "email": email,
        "status": status,
        "metadata": metadata or {},
    }
    logs = []
    try:
        if AUDIT_LOG_FILE.exists():
            with open(AUDIT_LOG_FILE, "r", encoding="utf-8") as f:
                logs = json.load(f)
    except Exception:
        logs = []
    logs.append(entry)
    logs = logs[-2000:]
    try:
        with open(AUDIT_LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(logs, f, indent=2)
    except Exception as exc:
        print(f"[WARN] Failed to persist audit log: {exc}")


def _load_audit_logs() -> list:
    try:
        with open(AUDIT_LOG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _load_activity_logs() -> list:
    try:
        if ACTIVITY_LOG_FILE.exists():
            with open(ACTIVITY_LOG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return []


def _save_activity_logs(logs: list) -> None:
    try:
        with open(ACTIVITY_LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(logs[-5000:], f, indent=2)
    except Exception as exc:
        print(f"[WARN] Failed to persist activity logs: {exc}")


def _activity_log(email: str | None, event: str, metadata: dict | None = None) -> None:
    logs = _load_activity_logs()
    logs.append(
        {
            "ts": int(time.time()),
            "email": email,
            "event": event,
            "metadata": metadata or {},
        }
    )
    _save_activity_logs(logs)


def _safe_send_otp(email: str, otp: str, is_resend: bool = False) -> bool:
    """Try SMTP first; fall back to console OTP in non-mail environments."""
    subject = "NovelNest Email Verification"
    body = (
        f"Your new OTP is {otp} (valid for 5 minutes)"
        if is_resend
        else f"Your OTP is {otp} (valid for 5 minutes)"
    )
    try:
        msg = Message(subject, sender=app.config["MAIL_USERNAME"], recipients=[email])
        msg.body = body
        mail.send(msg)
        return True
    except Exception as exc:
        print(f"[WARN] Failed to send OTP email: {exc}")
        send_otp_email(email, otp)
        return False


def _ensure_user_defaults(user: dict) -> dict:
    user.setdefault("role", "user")
    user.setdefault("mfa_enabled", False)
    user.setdefault("totp_secret", "")
    user.setdefault("survey_completed", False)
    user.setdefault("genres", [])
    user.setdefault("read_books", [])
    user.setdefault("loved_books", [])
    user.setdefault("checked_out_books", [])
    user.setdefault("profile", {"bio": "", "location": "", "phone": ""})
    return user


def _get_user(users: list, email: str):
    for u in users:
        if str(u.get("email", "")).lower() == email.lower():
            return _ensure_user_defaults(u)
    return None


def _post_login_target(user: dict) -> str:
    return "index" if user.get("survey_completed") else "survey"


def _complete_login(email: str, user: dict) -> None:
    session["logged_in"] = True
    session["email"] = email
    session["username"] = user.get("name", "User")
    session["role"] = user.get("role", "user")
    session.pop("pending_auth_email", None)
    session.pop("pending_auth_method", None)
    if user.get("survey_completed"):
        session["genre_ids"] = user.get("genres", [])
        session["read_book_ids"] = user.get("read_books", [])


def _admin_credentials() -> tuple[str, str, str]:
    admin_email = os.environ.get("ADMIN_EMAIL", "admin@novelnest.local").strip().lower()
    admin_name = os.environ.get("ADMIN_NAME", "NovelNest Administrator").strip() or "NovelNest Administrator"
    admin_password = os.environ.get("ADMIN_PASSWORD", "Admin@12345")
    return admin_email, admin_name, admin_password


def _ensure_admin_user(users: list) -> bool:
    admin_email, admin_name, admin_password = _admin_credentials()
    admin = _get_user(users, admin_email)
    if admin is None:
        users.append(
            {
                "email": admin_email,
                "password": generate_password_hash(admin_password),
                "name": admin_name,
                "survey_completed": True,
                "genres": [],
                "read_books": [],
                "checked_out_books": [],
                "role": "admin",
                "mfa_enabled": False,
                "totp_secret": pyotp.random_base32(),
                "profile": {"bio": "System administrator profile", "location": "", "phone": ""},
            }
        )
        print(f"[INFO] Admin account created: {admin_email}")
        return True
    changed = False
    if admin.get("role") != "admin":
        admin["role"] = "admin"
        changed = True
    if admin.get("name") != admin_name:
        admin["name"] = admin_name
        changed = True
    if not admin.get("password"):
        admin["password"] = generate_password_hash(admin_password)
        changed = True
    return changed


def _begin_auth_flow(email: str, user: dict, method: str):
    session["pending_auth_email"] = email
    session["pending_auth_method"] = method
    session["pending_auth_redirect"] = _post_login_target(user)
    if not user.get("totp_secret"):
        user["totp_secret"] = pyotp.random_base32()
        users = load_users()
        existing = _get_user(users, email)
        if existing is not None:
            existing["totp_secret"] = user["totp_secret"]
            save_users(users)
    if user.get("mfa_enabled"):
        return redirect(url_for("mfa_verify"))
    return redirect(url_for("mfa_setup"))

# ── App Setup ────────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY") or os.urandom(32)
app.config["PREFERRED_URL_SCHEME"] = os.environ.get("PREFERRED_URL_SCHEME", "http")
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = os.environ.get("SESSION_COOKIE_SAMESITE", "Lax")
app.config["SESSION_COOKIE_SECURE"] = _env_bool("SESSION_COOKIE_SECURE", False)
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=int(os.environ.get("SESSION_HOURS", "12")))
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

public_host = os.environ.get("PUBLIC_HOST", PUBLIC_SITE)
if public_host:
    app.config["SERVER_NAME"] = public_host

app.config["MAIL_SERVER"] = "smtp.gmail.com"
app.config["MAIL_PORT"] = 587
app.config["MAIL_USE_TLS"] = True
app.config["MAIL_USERNAME"] = os.environ.get("MAIL_USERNAME", "")
app.config["MAIL_PASSWORD"] = os.environ.get("MAIL_PASSWORD", "")

mail = Mail(app)
event_producer = KinesisEventProducer()


def _track_event(event_type: str, metadata: dict | None = None) -> None:
    try:
        uid = session.get("email") or session.get("proxy_uid")
        event_producer.publish_event(event_type=event_type, user_id=uid, metadata=metadata or {})
    except Exception:
        pass


# Basic in-memory login/signup rate guard (per IP + route).
_RL_WINDOW_SECS = 15 * 60
_RL_LIMIT = 20
_rl_events: dict[str, deque] = defaultdict(deque)


def _rate_guard(key: str, now_ts: float) -> bool:
    q = _rl_events[key]
    while q and now_ts - q[0] > _RL_WINDOW_SECS:
        q.popleft()
    if len(q) >= _RL_LIMIT:
        return False
    q.append(now_ts)
    return True

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "").strip()
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "").strip()
GOOGLE_OAUTH_ENABLED = bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET)
if GOOGLE_OAUTH_ENABLED:
    google_bp = make_google_blueprint(
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
        scope=[
            "openid",
            "https://www.googleapis.com/auth/userinfo.email",
            "https://www.googleapis.com/auth/userinfo.profile",
        ],
    )
    app.register_blueprint(google_bp, url_prefix="/login")

@app.before_request
def restore_user_session():
    if request.method == "POST" and request.path in {"/email-login", "/signup", "/forgot-password", "/verify-signup-otp"}:
        ip = request.headers.get("X-Forwarded-For", request.remote_addr or "unknown").split(",")[0].strip()
        key = f"{request.path}:{ip}"
        if not _rate_guard(key, time.time()):
            if request.path == "/signup":
                return render_template("signup.html", error="Too many attempts. Please wait and try again."), 429
            if request.path == "/verify-signup-otp":
                return render_template("verify_signup.html", error="Too many attempts. Please wait and try again."), 429
            return render_template("login.html", error="Too many login attempts. Please try again later."), 429

    # Only try to restore session loosely. Avoid making synchronous external HTTP requests.
    if GOOGLE_OAUTH_ENABLED and google.authorized and not session.get("logged_in"):
        # We redirect them to re-initiate login properly.
        pass


@app.after_request
def add_security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
    csp = "default-src 'self' https: data:; img-src 'self' https: data:; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com data:; script-src 'self' 'unsafe-inline' https:;"
    response.headers.setdefault("Content-Security-Policy", csp)
    return response

# ── Load Data & Init Recommenders ───────────────────────────
print("📚 Loading data…")
loader = DataLoader()
# Sample ratings securely to prevent OOM 'Killed' error on AWS instances (typically 1GB RAM limits)
books_df, users_df, ratings_df = loader.load_all(sample_ratings=150000)

print("📊 BOOKS DF COLUMNS:", books_df.columns)

if books_df is None or ratings_df is None:
    raise RuntimeError(
        "Failed to load data. Run `python data_loader.py` first."
    )

print("🧠 Initialising recommendation engines…")
recommender = HybridRecommender(books_df, ratings_df, users_df, loader=loader)

# ── Genre catalogue for the survey ──────────────────────────
SURVEY_GENRES = [
    {"id": "fiction",           "label": "Fiction",           "emoji": "✍️",  "tags": ["fiction"]},
    {"id": "fantasy",           "label": "Fantasy",           "emoji": "🧙",  "tags": ["fantasy", "magic", "urban-fantasy"]},
    {"id": "science-fiction",   "label": "Sci-Fi",            "emoji": "🚀",  "tags": ["science-fiction", "sci-fi"]},
    {"id": "mystery",           "label": "Mystery",           "emoji": "🔍",  "tags": ["mystery"]},
    {"id": "crime",             "label": "Crime & Detective", "emoji": "🕵️",  "tags": ["crime", "detective", "true-crime"]},
    {"id": "thriller",          "label": "Thriller",          "emoji": "😱",  "tags": ["thriller", "suspense"]},
    {"id": "romance",           "label": "Romance",           "emoji": "💕",  "tags": ["romance", "chick-lit", "paranormal-romance"]},
    {"id": "historical-fiction","label": "Historical Fiction","emoji": "🏰",  "tags": ["historical-fiction", "historical"]},
    {"id": "non-fiction",       "label": "Non-Fiction",       "emoji": "📰",  "tags": ["non-fiction", "nonfiction"]},
    {"id": "young-adult",       "label": "Young Adult",       "emoji": "🌟",  "tags": ["young-adult", "ya"]},
    {"id": "new-adult",         "label": "New Adult",         "emoji": "🎓",  "tags": ["new-adult"]},
    {"id": "classics",          "label": "Classics",          "emoji": "🏛️",  "tags": ["classics", "classic", "literature"]},
    {"id": "horror",            "label": "Horror",            "emoji": "👻",  "tags": ["horror", "vampires"]},
    {"id": "paranormal",        "label": "Paranormal",        "emoji": "🔮",  "tags": ["paranormal", "supernatural"]},
    {"id": "dystopian",         "label": "Dystopian",         "emoji": "🌆",  "tags": ["dystopian", "dystopia"]},
    {"id": "contemporary",      "label": "Contemporary",      "emoji": "🌍",  "tags": ["contemporary", "adult-fiction"]},
    {"id": "adventure",         "label": "Adventure",         "emoji": "⚔️",  "tags": ["adventure"]},
    {"id": "western",           "label": "Western",           "emoji": "🤠",  "tags": ["western", "cowboys"]},
    {"id": "children",          "label": "Children's",        "emoji": "🧒",  "tags": ["childrens", "children", "children-s"]},
    {"id": "middle-grade",      "label": "Middle Grade",      "emoji": "🎒",  "tags": ["middle-grade"]},
    {"id": "graphic-novels",    "label": "Comics & Manga",    "emoji": "🎨",  "tags": ["graphic-novels", "comics", "manga"]},
    {"id": "memoir",            "label": "Memoir",            "emoji": "📓",  "tags": ["memoir", "autobiography"]},
    {"id": "biography",         "label": "Biography",         "emoji": "👤",  "tags": ["biography", "biographies"]},
    {"id": "history",           "label": "History",           "emoji": "📜",  "tags": ["history", "historical"]},
    {"id": "self-help",         "label": "Self-Help",         "emoji": "💪",  "tags": ["self-help", "personal-development"]},
    {"id": "psychology",        "label": "Psychology",        "emoji": "🧠",  "tags": ["psychology"]},
    {"id": "science",           "label": "Science",           "emoji": "🔬",  "tags": ["science"]},
    {"id": "philosophy",        "label": "Philosophy",        "emoji": "🤔",  "tags": ["philosophy"]},
    {"id": "religion",          "label": "Religion & Spirituality", "emoji": "🙏",  "tags": ["religion", "spirituality", "christian"]},
    {"id": "business",          "label": "Business & Economics", "emoji": "💼",  "tags": ["business", "economics"]},
    {"id": "travel",            "label": "Travel",            "emoji": "✈️",  "tags": ["travel"]},
    {"id": "cookbooks",         "label": "Cookbooks & Food",  "emoji": "🍳",  "tags": ["cookbooks", "food", "cooking"]},
    {"id": "art",               "label": "Art & Photography", "emoji": "🖼️",  "tags": ["art", "photography"]},
    {"id": "humor",             "label": "Humor",             "emoji": "😂",  "tags": ["humor", "comedy"]},
    {"id": "satire",            "label": "Satire",            "emoji": "🎪",  "tags": ["satire"]},
    {"id": "poetry",            "label": "Poetry",            "emoji": "✒️",  "tags": ["poetry"]},
    {"id": "short-stories",     "label": "Short Stories",     "emoji": "📚",  "tags": ["short-stories"]},
    {"id": "essays",            "label": "Essays",            "emoji": "📝",  "tags": ["essays"]},
    {"id": "drama",             "label": "Drama & Plays",     "emoji": "🎭",  "tags": ["drama", "plays"]},
    {"id": "fairy-tales",       "label": "Fairy Tales & Folklore", "emoji": "🧚",  "tags": ["fairy-tales", "folklore", "mythology"]},
    {"id": "lgbtq",             "label": "LGBTQ+",            "emoji": "🏳️‍🌈", "tags": ["lgbt", "lgbtq", "queer"]},
    {"id": "political",         "label": "Political",         "emoji": "🗳️",  "tags": ["politics", "political"]},
]

# Precompute active real-user pool for CF proxy mapping
_active_users = (
    ratings_df["user_id"]
    .value_counts()
    .loc[lambda s: s >= 10]
    .index.tolist()
)

# Precompute strict top tags per book to avoid weak genre associations (like 1984 as horror)
_strict_book_tags = (
    loader.book_tags_df.groupby("goodreads_book_id").head(30)
    if loader.book_tags_df is not None else None
)


# ── Helpers ──────────────────────────────────────────────────

def _get_stats() -> dict:
    return {
        "books":   f"{len(books_df):,}",
        "ratings": f"{len(ratings_df):,}",
        "users":   f"{ratings_df['user_id'].nunique():,}",
    }


def _df_to_dicts(df, n=10):
    if df is None or df.empty:
        return []
    return df.head(n).to_dict("records")


def _book_title_from_id(book_id: int) -> str:
    try:
        row = books_df[books_df["book_id"] == int(book_id)]
        if not row.empty:
            return str(row.iloc[0].get("title", f"Book #{book_id}"))
    except Exception:
        pass
    return f"Book #{book_id}"


def _add_avg_rating(df):
    if df is None or df.empty:
        return df
    if "avg_rating" not in df.columns:
        book_ratings = (
            ratings_df.groupby("book_id")["rating"]
            .mean().reset_index()
            .rename(columns={"rating": "avg_rating"})
        )
        df = df.merge(book_ratings, on="book_id", how="left")
    return df


def _book_grid_html(items):
    if not items:
        return '<div class="empty-state"><div class="empty-state__icon">📚</div><div class="empty-state__text">No recommendations available</div></div>'
    html = '<div class="book-grid">'
    for b in items:
        html += _book_card_html(b)
    html += '</div>'
    return html


def _book_card_html(b):
    book_id = b.get("book_id", "")
    img = b.get("image_url_m") or b.get("image_url_l") or "https://via.placeholder.com/180x240?text=No+Cover"
    if pd.isna(img):
        img = "https://via.placeholder.com/180x240?text=No+Cover"

    title = str(b.get("title", "Unknown"))
    title_display = title[:50] + "…" if len(title) > 50 else title

    author = str(b.get("author", "Unknown"))
    author_display = author[:35] + "…" if len(author) > 35 else author

    rating_html = ""
    rating = b.get("avg_rating") or b.get("rating")
    if rating and not pd.isna(rating):
        rating_html = f'<div class="book-card__rating">⭐ {float(rating):.1f}</div>'

    return (
        f'<a href="/book/{book_id}" class="book-card">'
        f'<img class="book-card__img" src="{img}" alt="{title_display}" loading="lazy" '
        f'onerror="this.src=\'https://via.placeholder.com/180x240?text=No+Cover\'">'
        f'<div class="book-card__body">'
        f'<div class="book-card__title">{title_display}</div>'
        f'<div class="book-card__author">{author_display}</div>'
        f'{rating_html}'
        f'</div></a>'
    )


def _get_genre_book_ids(genre_ids: list) -> set:
    """Return book_ids that belong to any of the selected genres."""
    if not genre_ids or loader.tags_df is None or _strict_book_tags is None:
        return set()

    # Collect tag names for selected genre ids
    tag_names = []
    genre_map = {g["id"]: g["tags"] for g in SURVEY_GENRES}
    for gid in genre_ids:
        tag_names.extend(genre_map.get(gid, []))

    if not tag_names:
        return set()

    try:
        tag_ids = loader.tags_df[
            loader.tags_df["tag_name"].isin(tag_names)
        ]["tag_id"]
        goodreads_ids = _strict_book_tags[
            _strict_book_tags["tag_id"].isin(tag_ids)
        ]["goodreads_book_id"].unique()
        book_ids = set(
            books_df[books_df["goodreads_book_id"].isin(goodreads_ids)]["book_id"]
        )
        return book_ids
    except Exception:
        return set()


def _find_proxy_user(genre_ids: list, read_book_ids: list) -> int | None:
    """
    Find the real user whose rating history best matches the survey answers.
    Scoring: proportion of their top-rated books that are in selected genres.
    Falls back to a random active user.
    """
    genre_book_ids = _get_genre_book_ids(genre_ids)
    read_set = set(read_book_ids)

    if not genre_book_ids or not _active_users:
        return random.choice(_active_users) if _active_users else None

    # Sample up to 500 active users for speed
    candidates = _active_users[:500]

    best_uid, best_score = None, -1.0
    for uid in candidates:
        u_ratings = ratings_df[ratings_df["user_id"] == uid]
        if u_ratings.empty:
            continue
        # High-rated books (≥ 4)
        good_books = set(u_ratings[u_ratings["rating"] >= 4]["book_id"])
        if not good_books:
            continue
        intersect = good_books & genre_book_ids - read_set
        score = len(intersect) / len(good_books)
        if score > best_score:
            best_score = score
            best_uid = uid

    return best_uid if best_uid else random.choice(_active_users)


# ── Email Login ───────────────────────────────────────────


@app.route("/login")
def login_page():
    return render_template("login.html")

# ── Google Login ───────────────────────────────────────────


@app.route("/google-login")
def google_login():
    if not GOOGLE_OAUTH_ENABLED:
        return render_template(
            "login.html",
            error="Google Sign-In is not configured. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET.",
        )
    if not google.authorized:
        return redirect(url_for("google.login", prompt="select_account"))

    resp = google.get("/oauth2/v2/userinfo")
    user_info = resp.json()

    email = user_info["email"].strip().lower()

    users = load_users()
    user = _get_user(users, email)

    if user:
        _audit_log("google_login_attempt", email=email, status="success")
        return _begin_auth_flow(email, user, method="google")

    users.append({
        "email": email,
        "password": "",
        "name": user_info.get("name", "User"),
        "survey_completed": False,
        "genres": [],
        "read_books": [],
        "role": "user",
        "mfa_enabled": False,
        "totp_secret": pyotp.random_base32(),
    })

    save_users(users)
    _audit_log("google_signup", email=email, status="success")
    return _begin_auth_flow(email, _get_user(users, email), method="google")

def load_users():
    users = _load_users_from_s3() if _use_s3_users() else _load_users_from_local()
    changed = False
    if _ensure_admin_user(users):
        changed = True
    for user in users:
        before = dict(user)
        _ensure_user_defaults(user)
        if before != user:
            changed = True
    if changed:
        save_users(users)
    return users


def save_users(users: list) -> None:
    if _use_s3_users():
        _save_users_to_s3(users)
        return
    _save_users_to_local(users)


def _admin_only_redirect():
    if not session.get("logged_in"):
        return redirect(url_for("login_page"))
    if session.get("role") != "admin":
        flash("Admin access required.", "warning")
        return redirect(url_for("index"))
    return None


def _safe_int_list(values) -> list[int]:
    out: list[int] = []
    for v in values or []:
        try:
            out.append(int(v))
        except Exception:
            continue
    return out


def _safe_int_param(value, default: int, lo: int, hi: int) -> int:
    try:
        n = int(value)
    except Exception:
        return default
    return max(lo, min(hi, n))


def _admin_summary(users: list, activities: list) -> dict:
    checked_out_total = sum(len(_safe_int_list(u.get("checked_out_books", []))) for u in users)
    return {
        "users_count": len(users),
        "admins_count": sum(1 for u in users if u.get("role") == "admin"),
        "checked_out_total": checked_out_total,
        "activity_count": len(activities),
    }

@app.route("/email-login", methods=["POST"])
def email_login():
    email = request.form["email"].strip().lower()
    password = request.form["password"].strip()

    users = load_users()
    user = _get_user(users, email)

    if user:
        stored_password = user.get("password", "")

        # Google-only account (no local password set)
        if not stored_password:
            _audit_log("email_login", email=email, status="failed", metadata={"reason": "google_only_account"})
            return render_template("login.html", error="This account has no email password. Please use Google Sign-In.")

        password_ok = False
        try:
            if check_password_hash(stored_password, password):
                password_ok = True
        except Exception:
            # Ignore parse errors for legacy plain-text passwords.
            password_ok = False

        # Backward compatibility: allow old plain-text passwords once, then upgrade.
        if not password_ok and stored_password == password:
            password_ok = True
            user["password"] = generate_password_hash(password)
            save_users(users)

        if password_ok:
            _audit_log("email_login", email=email, status="success")
            return _begin_auth_flow(email, user, method="password")

    _audit_log("email_login", email=email, status="failed", metadata={"reason": "invalid_credentials"})
    return render_template("login.html", error="Invalid email or password ❌")


@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        users = load_users()
        user = _get_user(users, email)

        if not user:
            return render_template("forgot_password.html", step="email", error="No account found for this email.")

        otp = str(random.randint(100000, 999999))
        session["fp_email"] = email
        session["fp_otp"] = otp
        session["fp_otp_time"] = time.time()

        sent = _safe_send_otp(email, otp, is_resend=False)
        if not sent:
            flash("OTP email failed; OTP printed in server logs for testing.", "warning")
        return render_template("forgot_password.html", step="verify", email=email, success="OTP sent. Enter it to reset your password.")

    return render_template("forgot_password.html", step="email")


@app.route("/forgot-password/verify", methods=["POST"])
def forgot_password_verify():
    email = (session.get("fp_email") or "").strip().lower()
    if not email:
        return redirect(url_for("forgot_password"))

    entered_otp = request.form.get("otp", "").strip()
    new_password = request.form.get("new_password", "").strip()

    if time.time() - session.get("fp_otp_time", 0) > 300:
        session.pop("fp_email", None)
        session.pop("fp_otp", None)
        session.pop("fp_otp_time", None)
        return render_template("forgot_password.html", step="email", error="OTP expired. Request a new one.")

    if entered_otp != session.get("fp_otp"):
        return render_template("forgot_password.html", step="verify", email=email, error="Invalid OTP.")

    if len(new_password) < 8 or not any(ch.isupper() for ch in new_password) or not any(ch.isdigit() for ch in new_password):
        return render_template(
            "forgot_password.html",
            step="verify",
            email=email,
            error="Password must be at least 8 chars and include one uppercase letter and one number.",
        )

    users = load_users()
    user = _get_user(users, email)
    if not user:
        return render_template("forgot_password.html", step="email", error="Account not found. Please try again.")

    user["password"] = generate_password_hash(new_password)
    save_users(users)
    session.pop("fp_email", None)
    session.pop("fp_otp", None)
    session.pop("fp_otp_time", None)

    _audit_log("password_reset", email=email, status="success")
    return render_template("login.html", success="Password reset successful. Please log in.")


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"].strip().lower()
        password = request.form["password"]

        users = load_users()

        if any(u["email"] == email for u in users):
            return render_template("signup.html", error="Email already exists ❌")

        otp = str(random.randint(100000, 999999))

        session["temp_user"] = {
            "name": name,
            "email": email,
            "password": password,
            "role": "user",
            "mfa_enabled": False,
            "totp_secret": pyotp.random_base32(),
        }
        session["signup_otp"] = otp
        session["otp_time"] = time.time()

        sent = _safe_send_otp(email, otp, is_resend=False)
        if not sent:
            flash("Could not send OTP email right now. OTP printed in server logs for testing.", "warning")

        return redirect(url_for("verify_signup_otp"))

    return render_template("signup.html")

@app.route("/verify-signup-otp", methods=["GET", "POST"])
def verify_signup_otp():

    if request.method == "POST":
        entered = request.form.get("otp", "").strip()

        # ⏱ Check expiry
        if time.time() - session.get("otp_time", 0) > 300:
            return render_template("verify_signup.html", error="OTP expired ❌")

        # ✅ Check OTP
        if entered == session.get("signup_otp"):
            user_data = session.get("temp_user")

            if not user_data:
                return redirect(url_for("signup"))

            users = load_users()

            users.append({
                "email": user_data["email"],
                "password": generate_password_hash(user_data["password"]),
                "name": user_data["name"],
                "survey_completed": False,
                "genres": [],
                "read_books": [],
                "role": user_data.get("role", "user"),
                "mfa_enabled": user_data.get("mfa_enabled", False),
                "totp_secret": user_data.get("totp_secret", ""),
            })

            save_users(users)

            # 🧹 Clear session
            session.pop("signup_otp", None)
            session.pop("temp_user", None)
            session.pop("otp_time", None)

            return redirect(url_for("login_page"))

        # ❌ Wrong OTP
        return render_template("verify_signup.html", error="Invalid OTP ❌")

    # GET request
    return render_template("verify_signup.html")


@app.route("/mfa/setup", methods=["GET", "POST"])
def mfa_setup():
    pending_email = session.get("pending_auth_email")
    if not pending_email:
        return redirect(url_for("login_page"))
    users = load_users()
    user = _get_user(users, pending_email)
    if not user:
        return redirect(url_for("login_page"))
    secret = user.get("totp_secret") or pyotp.random_base32()
    if user.get("totp_secret") != secret:
        user["totp_secret"] = secret
        save_users(users)

    totp = pyotp.TOTP(secret)
    provisioning_uri = totp.provisioning_uri(name=pending_email, issuer_name="NovelNest")

    if request.method == "POST":
        code = request.form.get("code", "").strip()
        if totp.verify(code, valid_window=1):
            user["mfa_enabled"] = True
            save_users(users)
            _complete_login(pending_email, user)
            _audit_log("mfa_setup_complete", email=pending_email, status="success")
            return redirect(url_for(session.pop("pending_auth_redirect", "index")))
        _audit_log("mfa_setup_complete", email=pending_email, status="failed")
        return render_template("mfa_setup.html", secret=secret, provisioning_uri=provisioning_uri, error="Invalid code.")

    return render_template("mfa_setup.html", secret=secret, provisioning_uri=provisioning_uri)


@app.route("/mfa/verify", methods=["GET", "POST"])
def mfa_verify():
    pending_email = session.get("pending_auth_email")
    if not pending_email:
        return redirect(url_for("login_page"))
    users = load_users()
    user = _get_user(users, pending_email)
    if not user:
        return redirect(url_for("login_page"))

    secret = user.get("totp_secret", "")
    if not secret:
        return redirect(url_for("mfa_setup"))
    totp = pyotp.TOTP(secret)

    if request.method == "POST":
        code = request.form.get("code", "").strip()
        if totp.verify(code, valid_window=1):
            _complete_login(pending_email, user)
            _audit_log("mfa_verify", email=pending_email, status="success", metadata={"method": session.get("pending_auth_method")})
            return redirect(url_for(session.pop("pending_auth_redirect", "index")))
        _audit_log("mfa_verify", email=pending_email, status="failed", metadata={"method": session.get("pending_auth_method")})
        return render_template("mfa_verify.html", error="Invalid code.")

    return render_template("mfa_verify.html")


@app.route("/admin")
def admin_dashboard():
    guard = _admin_only_redirect()
    if guard is not None:
        return guard
    users = load_users()
    users_view = []
    for u in users:
        item = dict(u)
        item["encoded_email"] = quote(str(u.get("email", "")), safe="")
        users_view.append(item)
    logs = list(reversed(_load_audit_logs()))[:300]
    activities = list(reversed(_load_activity_logs()))[:300]
    return render_template(
        "admin_audit.html",
        logs=logs,
        activities=activities,
        users=users_view,
        summary=_admin_summary(users, activities),
        stats=_get_stats(),
        admin_email=_admin_credentials()[0],
    )


@app.route("/admin/audit")
def admin_audit_dashboard():
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/users/<path:email>/update", methods=["POST"])
def admin_user_update(email: str):
    guard = _admin_only_redirect()
    if guard is not None:
        return guard
    target_email = unquote(email).strip().lower()
    users = load_users()
    user = _get_user(users, target_email)
    if user is None:
        flash("User not found.", "error")
        return redirect(url_for("admin_dashboard"))

    user["name"] = request.form.get("name", user.get("name", "")).strip()[:80] or user.get("name", "User")
    role = request.form.get("role", user.get("role", "user")).strip().lower()
    user["role"] = "admin" if role == "admin" else "user"
    user["mfa_enabled"] = request.form.get("mfa_enabled") == "on"
    profile = user.get("profile", {})
    profile["bio"] = request.form.get("bio", profile.get("bio", "")).strip()[:280]
    profile["location"] = request.form.get("location", profile.get("location", "")).strip()[:80]
    profile["phone"] = request.form.get("phone", profile.get("phone", "")).strip()[:40]
    user["profile"] = profile

    new_password = request.form.get("new_password", "").strip()
    if new_password:
        user["password"] = generate_password_hash(new_password)

    save_users(users)
    _audit_log("admin_user_update", email=session.get("email"), metadata={"target_email": target_email, "role": user["role"]})
    _activity_log(session.get("email"), "admin_user_update", {"target_email": target_email})
    flash(f"Updated profile for {target_email}.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/users/<path:email>/checkout/clear", methods=["POST"])
def admin_clear_checkouts(email: str):
    guard = _admin_only_redirect()
    if guard is not None:
        return guard
    target_email = unquote(email).strip().lower()
    users = load_users()
    user = _get_user(users, target_email)
    if user is None:
        flash("User not found.", "error")
        return redirect(url_for("admin_dashboard"))
    user["checked_out_books"] = []
    save_users(users)
    _audit_log("admin_clear_checkouts", email=session.get("email"), metadata={"target_email": target_email})
    _activity_log(session.get("email"), "admin_clear_checkouts", {"target_email": target_email})
    flash(f"Cleared checkouts for {target_email}.", "success")
    return redirect(url_for("admin_dashboard"))

# ── Routes ───────────────────────────────────────────────────

@app.route("/")
def index():
    if not session.get("logged_in"):
        return redirect(url_for("login_page"))

    users = load_users()
    user = next((u for u in users if u.get("email") == session.get("email")), None)
    
    if not user or not user.get("survey_completed"):
        return redirect(url_for("survey"))

    return render_template(
        "index.html",
        stats=_get_stats(),
    )


@app.route("/discover")
def discover():
    if not session.get("logged_in"):
        return redirect(url_for("login_page"))
    users = load_users()
    user = next((u for u in users if u.get("email") == session.get("email")), None)
    if not user or not user.get("survey_completed"):
        return redirect(url_for("onboarding"))
    return render_template("discover.html", stats=_get_stats())


@app.route("/browse")
def browse():
    if not session.get("username"):
        return redirect(url_for("onboarding"))

    query = request.args.get("q", "").strip()
    selected_genre = request.args.get("genre", "").strip().lower()
    books = []

    if query:
        source = recommender.content.search_books(query, n=60)
    else:
        source = recommender.popularity.get_best_books(n=60)

    if not source.empty and selected_genre:
        keep_ids = _get_genre_book_ids([selected_genre])
        if keep_ids:
            source = source[source["book_id"].isin(keep_ids)]
        else:
            source = source.iloc[0:0]

    books = _df_to_dicts(source, n=24) if not source.empty else []
    return render_template(
        "browse.html",
        query=query,
        books=books,
        selected_genre=selected_genre,
        genres=SURVEY_GENRES,
        stats=_get_stats(),
    )


@app.route("/onboarding")
def onboarding():
    if not session.get("logged_in"):
        return redirect(url_for("login_page"))
    users = load_users()
    user = next((u for u in users if u.get("email") == session.get("email")), None)
    survey_done = bool(user and user.get("survey_completed"))
    return render_template("onboarding.html", survey_done=survey_done, stats=_get_stats())


@app.route("/books/<int:book_id>")
def books_detail_alias(book_id):
    return redirect(url_for("book_detail", book_id=book_id))



# ── Survey ───────────────────────────────────────────────────

@app.route("/survey")
def survey():
    if not session.get("logged_in"):
        return redirect(url_for("login_page"))
        
    users = load_users()
    user = next((u for u in users if u.get("email") == session.get("email")), None)
    force_mode = request.args.get("force", "").strip().lower() in {"1", "true", "yes"}
    if user and user.get("survey_completed") and not force_mode:
        return redirect(url_for("index"))

    return render_template(
        "survey.html",
        genres=SURVEY_GENRES,
        stats=_get_stats(),
    )


@app.route("/survey/submit", methods=["POST"])
def survey_submit():
    data = request.get_json(silent=True) or {}

    username   = str(data.get("username", "Reader")).strip()[:40] or "Reader"
    genre_ids  = [str(g) for g in data.get("genres", [])]
    read_books = [int(b) for b in data.get("read_books", []) if str(b).isdigit()]

    proxy_uid = _find_proxy_user(genre_ids, read_books)

    session["username"]      = username
    session["genres"]        = [g["label"] for g in SURVEY_GENRES if g["id"] in genre_ids]
    session["genre_ids"]     = genre_ids
    session["read_book_ids"] = read_books
    session["proxy_uid"]     = proxy_uid
    _track_event(
        "survey_submit",
        {"genres_count": len(genre_ids), "read_books_count": len(read_books), "proxy_uid": proxy_uid},
    )
    _activity_log(
        session.get("email"),
        "survey_submit",
        {"genres_count": len(genre_ids), "read_books_count": len(read_books), "proxy_uid": proxy_uid},
    )

    # 🔥 SAVE TO users.json (THIS WAS MISSING)
    users = load_users()

    updated = False

    for user in users:
        if user.get("email") == session.get("email"):
            user["name"] = username
            user["genres"] = genre_ids
            user["read_books"] = read_books
            user["survey_completed"] = True
            updated = True
            break

    # 🔥 IMPORTANT: if user not found → create it
    if not updated:
        users.append({
            "email": session.get("email"),
            "password": "",
            "name": username,
            "genres": genre_ids,
            "read_books": read_books,
            "survey_completed": True
        })

    save_users(users)

    return jsonify(ok=True)



@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login_page"))


@app.route("/profile")
def profile():
    if not session.get("logged_in"):
        return redirect(url_for("login_page"))

    users = load_users()
    user = _get_user(users, session.get("email", ""))
    if user is None:
        flash("Profile not found.", "warning")
        return redirect(url_for("index"))

    checked_out_ids = _safe_int_list(user.get("checked_out_books", []))
    read_ids = _safe_int_list(user.get("read_books", []))
    loved_ids = _safe_int_list(user.get("loved_books", []))

    checked_out_books = []
    read_books = []
    loved_books = []
    if checked_out_ids:
        checked_out_books = books_df[books_df["book_id"].isin(checked_out_ids)].to_dict("records")
    if read_ids:
        read_books = books_df[books_df["book_id"].isin(read_ids)].to_dict("records")
    if loved_ids:
        loved_books = books_df[books_df["book_id"].isin(loved_ids)].to_dict("records")

    return render_template(
        "profile.html",
        user=user,
        checked_out_books=checked_out_books,
        read_books=read_books,
        loved_books=loved_books,
        stats=_get_stats(),
    )


@app.route("/profile/reset", methods=["POST"])
def profile_reset():
    if not session.get("logged_in"):
        return redirect(url_for("login_page"))
    users = load_users()
    user = _get_user(users, session.get("email", ""))
    if user is None:
        flash("Profile not found.", "warning")
        return redirect(url_for("index"))

    user["read_books"] = []
    user["loved_books"] = []
    user["checked_out_books"] = []
    user["genres"] = []
    user["survey_completed"] = False
    save_users(users)

    session["read_book_ids"] = []
    session["genre_ids"] = []
    session["genres"] = []
    flash("Profile preferences reset. Please complete onboarding again.", "success")
    return redirect(url_for("onboarding"))


@app.route("/resend-otp")
def resend_otp():
    import time, random

    if "temp_user" not in session:
        return redirect(url_for("signup"))

    last_time = session.get("otp_time", 0)
    remaining = 30 - (time.time() - last_time)

    if remaining > 0:
        flash(f"Wait {int(remaining)} sec before resending ⏳")
        return redirect(url_for("verify_signup_otp"))

    otp = str(random.randint(100000, 999999))

    session["signup_otp"] = otp
    session["otp_time"] = time.time()

    sent = _safe_send_otp(session["temp_user"]["email"], otp, is_resend=True)
    if sent:
        flash("New OTP sent ✅")
    else:
        flash("Could not send OTP email right now. OTP printed in server logs for testing.", "warning")

    return redirect(url_for("verify_signup_otp"))

# ── Book Detail ──────────────────────────────────────────────

@app.route("/book/<int:book_id>")
def book_detail(book_id):
    if not session.get("username"):
        return redirect(url_for("survey"))

    book_row = books_df[books_df["book_id"] == book_id]
    if book_row.empty:
        flash("Book not found.", "warning")
        return redirect(url_for("index"))

    book = book_row.iloc[0].to_dict()
    genres = loader.get_book_genres(book_id, top_n=8)

    users = load_users()
    user = _get_user(users, session.get("email", ""))
    if user is not None:
        checked_out = _safe_int_list(user.get("checked_out_books", []))
        if book_id not in checked_out:
            checked_out.append(book_id)
            user["checked_out_books"] = checked_out
            save_users(users)

    similar = recommender.content.get_similar_to_book(book_id, n=10)
    similar_books = _df_to_dicts(similar)
    _track_event("book_view", {"book_id": book_id})
    _activity_log(
        session.get("email"),
        "book_view",
        {"book_id": book_id, "title": _book_title_from_id(book_id)},
    )

    return render_template(
        "book_detail.html",
        book=book,
        genres=genres,
        similar_books=similar_books,
        is_read=book_id in set(_safe_int_list(user.get("read_books", []))) if user else False,
        is_loved=book_id in set(_safe_int_list(user.get("loved_books", []))) if user else False,
        stats=_get_stats(),
    )


@app.route("/book/<int:book_id>/track/<action>", methods=["POST"])
def track_book(book_id: int, action: str):
    if not session.get("logged_in"):
        return redirect(url_for("login_page"))

    users = load_users()
    user = _get_user(users, session.get("email", ""))
    if user is None:
        flash("User profile not found.", "error")
        return redirect(url_for("index"))

    if action not in {"read", "love"}:
        flash("Unknown action.", "warning")
        return redirect(request.referrer or url_for("book_detail", book_id=book_id))

    key = "read_books" if action == "read" else "loved_books"
    label = "read" if action == "read" else "loved"

    tracked = _safe_int_list(user.get(key, []))
    if book_id not in tracked:
        tracked.append(book_id)
        user[key] = tracked
        save_users(users)
        if action == "read":
            session["read_book_ids"] = tracked
        _audit_log(f"book_mark_{label}", email=session.get("email"), metadata={"book_id": book_id})
        _activity_log(session.get("email"), f"book_mark_{label}", {"book_id": book_id, "title": _book_title_from_id(book_id)})
        flash(f"Book marked as {label}.", "success")
    else:
        tracked = [b for b in tracked if b != book_id]
        user[key] = tracked
        save_users(users)
        if action == "read":
            session["read_book_ids"] = tracked
        flash(f"Book removed from {label} list.", "info")

    return redirect(request.referrer or url_for("book_detail", book_id=book_id))


# ── Search ───────────────────────────────────────────────────

@app.route("/search")
def search():
    if not session.get("username"):
        return redirect(url_for("survey"))

    query = request.args.get("q", "").strip()
    books = []
    if query:
        results = recommender.content.search_books(query, n=20)
        books = _df_to_dicts(results, n=20)
        _track_event("search", {"query": query, "results_count": len(books)})
        _activity_log(session.get("email"), "search", {"query": query, "results_count": len(books)})
    return render_template(
        "search_results.html",
        query=query,
        books=books,
        stats=_get_stats(),
    )


# ── API: Book search (for survey autocomplete) ───────────────

@app.route("/api/book_search")
def api_book_search():
    q = request.args.get("q", "").strip()
    n = _safe_int_param(request.args.get("n", 8), default=8, lo=1, hi=20)
    if not q or len(q) < 2:
        return jsonify(books=[])
    results = recommender.content.search_books(q, n=n)
    out_cols = ["book_id", "title", "author", "image_url_m", "avg_rating"]
    cols = [c for c in out_cols if c in results.columns]
    out = results[cols].to_dict("records") if not results.empty else []
    _track_event("api_book_search", {"query": q, "results_count": len(out)})
    _activity_log(session.get("email"), "api_book_search", {"query": q, "results_count": len(out)})
    return jsonify(books=out)


# ── API: Recommendation tabs ─────────────────────────────────

@app.route("/api/recommendations/<tab>")
def api_recommendations(tab):
    if not session.get("username"):
        return '<div class="alert alert--warning">Please complete the survey first.</div>'

    proxy_uid     = session.get("proxy_uid")
    genre_ids     = session.get("genre_ids", [])
    read_book_ids = set(session.get("read_book_ids", []))

    if tab == "foryou":
        return _render_foryou(proxy_uid, genre_ids, read_book_ids)
    elif tab == "popular":
        return _render_popular(genre_ids)
    elif tab == "author":
        return _render_author(proxy_uid, genre_ids)
    elif tab == "personalized":
        return _render_personalized(proxy_uid, read_book_ids, genre_ids)
    else:
        return '<div class="alert alert--warning">Unknown tab.</div>'


def _render_foryou(proxy_uid, genre_ids, read_book_ids):
    h2  = '<h2 class="section-header">🔥 Recommended For You</h2>'
    sub = f'<p class="section-sub">Personalised picks based on your survey, {session.get("username", "Reader")}!</p>'

    genre_book_ids = _get_genre_book_ids(genre_ids) if genre_ids else set()

    # Request more recommendations initially as we will filter them down
    recs = recommender.get_recommendations(user_id=proxy_uid, n=150)
    recs = _add_avg_rating(recs)

    # Filter out already-read books
    if not recs.empty and read_book_ids:
        recs = recs[~recs["book_id"].isin(read_book_ids)]

    # STRICT FILTER: Only keep recommendations that match selected genres
    if not recs.empty and genre_book_ids:
        recs = recs[recs["book_id"].isin(genre_book_ids)]

    items = _df_to_dicts(recs, n=12)
    if not items:
        return h2 + '<div class="alert alert--info">No personal recommendations found in your selected genres. Try adding more categories to your survey!</div>'
    return h2 + sub + _book_grid_html(items)


def _render_popular(genre_ids):
    html = '<h2 class="section-header">⭐ Top Rated</h2>'

    genre_book_ids = _get_genre_book_ids(genre_ids) if genre_ids else set()

    top = recommender.popularity.get_best_books(n=100)
    
    # Strict genre filtering
    if genre_book_ids and not top.empty:
        top = top[top["book_id"].isin(genre_book_ids)]

    top_books = top.head(12)
    if not top_books.empty:
        html += '<p class="section-sub">Top-rated books in your favourite genres</p>'
        html += _book_grid_html(_df_to_dicts(top_books))
    else:
        html += '<div class="alert alert--info">No popular books found in your selected genres.</div>'

    return html


def _render_author(proxy_uid, genre_ids):
    html = '<h2 class="section-header">📖 Explore by Author</h2>'
    if proxy_uid is None:
        return html + '<div class="alert alert--info">Complete the survey to discover authors.</div>'

    user_ratings = ratings_df[ratings_df["user_id"] == proxy_uid]
    if user_ratings.empty:
        return html + '<div class="alert alert--info">No author data for your profile.</div>'

    user_books = user_ratings.merge(books_df, on="book_id")
    if "author" not in user_books.columns:
        return html + '<div class="alert alert--info">No author data available.</div>'
        
    genre_book_ids = _get_genre_book_ids(genre_ids) if genre_ids else set()

    fav_authors = user_books.nlargest(5, "rating")["author"].unique()
    html += '<p class="section-sub">Based on authors you might enjoy</p>'

    authors_shown = 0
    for author in fav_authors:
        if authors_shown >= 3:
            break
        if pd.notna(author):
            author_books = recommender.content.get_similar_by_author(author, n=20)
            if not author_books.empty and genre_book_ids:
                author_books = author_books[author_books["book_id"].isin(genre_book_ids)]
                
            if not author_books.empty:
                html += f'<div class="author-section"><div class="author-section__name">{author}</div>'
                html += '<div class="book-row">'
                for b in author_books.head(5).to_dict("records"):
                    html += _book_card_html(b)
                html += '</div></div>'
                authors_shown += 1
                
    if authors_shown == 0:
        html += '<div class="alert alert--info">No author recommendations found in your selected genres.</div>'
        
    return html


def _render_personalized(proxy_uid, read_book_ids, genre_ids):
    html = '<h2 class="section-header">🎯 Because You Might Like…</h2>'
    
    genre_book_ids = _get_genre_book_ids(genre_ids) if genre_ids else set()
    has_results = False

    if read_book_ids:
        # Use the user's listed read books as anchors for "because you read"
        html += '<p class="section-sub">Based on books you\'ve already read</p>'
        shown = 0
        for book_id in list(read_book_ids)[:3]:
            book_info = books_df[books_df["book_id"] == book_id]
            if book_info.empty:
                continue
            title = book_info.iloc[0].get("title", str(book_id))
            similar = recommender.content.get_similar_to_book(book_id, n=25)
            if similar is not None and not similar.empty:
                similar = similar[~similar["book_id"].isin(read_book_ids)]
                
                if genre_book_ids:
                    similar = similar[similar["book_id"].isin(genre_book_ids)]
                    
                if not similar.empty:
                    html += f'<div class="because-section">'
                    html += f'<div class="because-section__label">Because you read <strong>{title}</strong></div>'
                    html += '<div class="book-row">'
                    for b in similar.head(5).to_dict("records"):
                        html += _book_card_html(b)
                    html += '</div></div>'
                    shown += 1
                    has_results = True

        if shown > 0:
            return html

    # Fallback: CF-based if proxy user available
    if proxy_uid:
        because = recommender.get_because_you_read(proxy_uid, n=20)
        if because:
            if not has_results:
                html += '<p class="section-sub">Books you might enjoy based on your taste</p>'
            for source_title, recs_df in because.items():
                if recs_df is not None and not recs_df.empty:
                    if genre_book_ids:
                        recs_df = recs_df[recs_df["book_id"].isin(genre_book_ids)]
                        
                    if not recs_df.empty:
                        html += f'<div class="because-section">'
                        html += f'<div class="because-section__label">Because you might enjoy books like <strong>{source_title}</strong></div>'
                        html += '<div class="book-row">'
                        for b in recs_df.head(5).to_dict("records"):
                            html += _book_card_html(b)
                        html += '</div></div>'
                        has_results = True

    if not has_results:
        html += '<div class="alert alert--info">Complete the survey and add more categories to get personalized picks!</div>'
        
    return html


# ── Run ──────────────────────────────────────────────────────

if __name__ == "__main__":
    print()
    print("=" * 60)
    print("🚀 NOVEL NEST IS LIVE!")
    print("👉 Website hosted at: http://13.204.232.136:5000")
    print("=" * 60)
    print()
    app.run(host="0.0.0.0", port=5000, debug=False)
