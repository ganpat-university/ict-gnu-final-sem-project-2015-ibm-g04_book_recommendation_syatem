# NovelNest FastAPI Backend

Run locally:

```bash
cd apps/api
uvicorn app.main:app --reload --port 5000
```

Swagger:
- `http://13.204.232.136:5000/docs`

Environment variables:
- `DATABASE_URL`
- `JWT_SECRET`
- `REDIS_URL`
