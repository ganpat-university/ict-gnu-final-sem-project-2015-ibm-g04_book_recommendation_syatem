# NovelNest Production Architecture

## Services
- `apps/web`: Next.js frontend with Tailwind and Framer Motion.
- `apps/api`: FastAPI backend with modular routes and JWT auth.
- `ml/training`: SVD + NCF training/evaluation notes and scripts.
- `ml/inference`: hybrid ranker contract.

## API Endpoints
- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `GET /api/v1/books`
- `GET /api/v1/search`
- `GET /api/v1/search/suggest`
- `GET /api/v1/recommend`
- `POST /api/v1/user/activity`

## Deployment
- Frontend: S3 + CloudFront (or Vercel)
- API: EC2/ECS with `uvicorn`
- Database: PostgreSQL (RDS)
- Cache: Redis (ElastiCache)
- Models + static assets: S3
