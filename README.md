# 📚 NovelNest - Intelligent Book Recommendation System

A sophisticated hybrid book recommendation system powered by Flask, combining multiple recommendation algorithms with survey-driven personalization. Uses the **goodbooks-10k** dataset with 10,000 books and 6 million ratings.

## 🚀 Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run the application
python app.py
```

Open http://13.204.232.136:5000 in your browser.

## ☁️ Deploy On EC2 (Static IP)

Set environment variables before starting the app on your EC2 instance:

```bash
export HOST=0.0.0.0
export PORT=5000
export FLASK_DEBUG=false
export PUBLIC_HOST=13.204.232.136:5000
export PREFERRED_URL_SCHEME=http
```

Then run:

```bash
python app.py
```

Open in browser:
`http://13.204.232.136:5000`

## 🛡️ Production Deploy (Gunicorn + Nginx on EC2)

Use this to serve the app on your EC2 static IP on port `80` (and later `443`).

### 1) Install runtime packages

```bash
sudo apt update
sudo apt install -y python3-pip python3-venv nginx
```

### 2) Setup project virtualenv

```bash
cd /home/ubuntu/NOVEL-NEST-main
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3) Test Gunicorn locally on EC2

```bash
source .venv/bin/activate
export PREFERRED_URL_SCHEME=http
export OAUTHLIB_INSECURE_TRANSPORT=1
gunicorn --bind 127.0.0.1:8000 --workers 3 app:app
```

### 4) Create systemd service

Create `/etc/systemd/system/novelnest.service`:

```ini
[Unit]
Description=NovelNest Gunicorn Service
After=network.target

[Service]
User=ubuntu
Group=www-data
WorkingDirectory=/home/ubuntu/NOVEL-NEST-main
Environment="PATH=/home/ubuntu/NOVEL-NEST-main/.venv/bin"
Environment="PREFERRED_URL_SCHEME=http"
Environment="OAUTHLIB_INSECURE_TRANSPORT=1"
Environment="SECRET_KEY=change-this-in-production"
Environment="MAIL_USERNAME=your-mail@gmail.com"
Environment="MAIL_PASSWORD=your-app-password"
Environment="GOOGLE_CLIENT_ID=your-google-client-id"
Environment="GOOGLE_CLIENT_SECRET=your-google-client-secret"
ExecStart=/home/ubuntu/NOVEL-NEST-main/.venv/bin/gunicorn --workers 3 --bind 127.0.0.1:8000 app:app
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start it:

```bash
sudo systemctl daemon-reload
sudo systemctl enable novelnest
sudo systemctl start novelnest
sudo systemctl status novelnest
```

### 5) Configure Nginx reverse proxy

Create `/etc/nginx/sites-available/novelnest`:

```nginx
server {
    listen 80;
    server_name 13.204.232.136;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Enable Nginx site:

```bash
sudo ln -s /etc/nginx/sites-available/novelnest /etc/nginx/sites-enabled/novelnest
sudo nginx -t
sudo systemctl restart nginx
```

### 6) Security group rules

In EC2 Security Group, allow inbound:
- TCP `80` from `0.0.0.0/0`
- TCP `443` from `0.0.0.0/0` (when HTTPS is enabled)

### 7) (Optional) Enable HTTPS with Certbot

If you attach a domain to your EC2 IP:

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com -d www.your-domain.com
```

## ☁️ Use S3 For `data/` On EC2

The app now supports auto-syncing dataset files from S3 before loading data.

### 1) Upload data to S3

Upload your local `data/` contents to a bucket path:

```bash
aws s3 sync ./data s3://your-bucket/novelnest/data
```

Keep this exact structure in S3:
- `s3://your-bucket/novelnest/data/books.csv`
- `s3://your-bucket/novelnest/data/ratings.csv`
- `s3://your-bucket/novelnest/data/book_tags.csv`
- `s3://your-bucket/novelnest/data/tags.csv`

### 2) Attach IAM role to EC2

Attach an instance profile role with S3 read permissions.

Example IAM policy:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:ListBucket"],
      "Resource": "arn:aws:s3:::your-bucket"
    },
    {
      "Effect": "Allow",
      "Action": ["s3:GetObject"],
      "Resource": "arn:aws:s3:::your-bucket/novelnest/data/*"
    }
  ]
}
```

### 3) Install AWS CLI on EC2

```bash
sudo apt update
sudo apt install -y awscli
aws --version
```

### 4) Set app environment variables

Add these to your `novelnest.service`:

```ini
Environment="DATA_SOURCE=s3"
Environment="S3_DATA_URI=s3://your-bucket/novelnest/data"
Environment="S3_SYNC_DELETE=false"
Environment="USER_STORE=s3"
Environment="S3_USERS_URI=s3://your-bucket/novelnest/runtime/users.json"
```

- `DATA_SOURCE=s3`: enables S3 sync mode.
- `DATA_SOURCE=s3_direct`: reads CSV files directly from S3 (no local `data/` sync).
- `S3_DATA_URI`: S3 path that contains CSV files.
- `S3_SYNC_DELETE=true`: optional; removes local files not present in S3.
- `USER_STORE=s3`: store app runtime users in S3 instead of local `users.json`.
- `S3_USERS_URI`: full S3 path for runtime user data.

### 4.1) One-time upload of existing local runtime users

If you already have local users, upload them once:

```bash
aws s3 cp ./users.json s3://your-bucket/novelnest/runtime/users.json
```

The app will keep reading/writing this JSON object on each auth/survey update.

### 5) Restart service

```bash
sudo systemctl daemon-reload
sudo systemctl restart novelnest
sudo journalctl -u novelnest -f
```

Look for log lines similar to:
- `Syncing data from S3...`
- `S3 sync completed`

## Prototype Expansion: Kinesis + SVD + NCF

These are optional prototype tracks and are disabled by default.

### Environment Flags

Add as needed in your service:

```ini
Environment="AWS_REGION=ap-south-1"
Environment="ENABLE_KINESIS_EVENTS=false"
Environment="KINESIS_STREAM_NAME=novelnest-events"
Environment="KINESIS_PARTITION_KEY=novelnest"
Environment="KINESIS_BATCH_SIZE=100"
Environment="KINESIS_S3_RAW_PREFIX=s3://your-bucket/novelnest/interactions/raw"
Environment="KINESIS_S3_CURATED_PREFIX=s3://your-bucket/novelnest/interactions/curated"
Environment="ENABLE_SAGEMAKER_SVD=false"
Environment="SVD_ARTIFACT_S3_URI=s3://your-bucket/novelnest/models/svd/latest.json"
Environment="ENABLE_NCF=false"
Environment="NCF_ARTIFACT_S3_URI=s3://your-bucket/novelnest/models/ncf/latest.json"
```

### Kinesis Event Producer

When `ENABLE_KINESIS_EVENTS=true`, the app publishes events for:
- survey submission
- book detail views
- search and API search actions

If AWS/Kinesis is unavailable, the app silently falls back without failing requests.

### One-shot Kinesis Consumer

Run once to read records and sink to S3 JSONL:

```bash
python aws/kinesis_consumer.py
```

### Train SVD Artifact (prototype)

```bash
python training/svd_train.py \
  --interactions-uri s3://your-bucket/novelnest/interactions/curated \
  --out-s3-uri s3://your-bucket/novelnest/models/svd/latest.json \
  --factors 32
```

### Train Neural CF Artifact (prototype)

```bash
python training/ncf_train.py \
  --interactions-uri s3://your-bucket/novelnest/interactions/curated \
  --out-s3-uri s3://your-bucket/novelnest/models/ncf/latest.json \
  --factors 32 \
  --epochs 3
```

### Validation Scripts

```bash
python scripts/smoke_aws_prototypes.py
python scripts/e2e_prototype_flow.py
pytest -q tests/test_prototype_fallbacks.py
```

## ✨ Features

### Recommendation Algorithms
- **📊 Popularity-Based**: IMDB-style weighted ratings for trending books
- **📖 Content-Based**: TF-IDF title similarity + author matching
- **👥 Collaborative Filtering**: User-user similarity with proxy user mapping
- **🔀 Hybrid Ranking**: Smart blending with cold-start handling
- **🎯 Personalized Recommendations**: Survey-driven user profiling

### User Experience
- **📝 3-Step Survey**: Name → Genre preferences → Books read
- **🏷️ 43 Genre Categories**: Comprehensive genre selection from Fiction to LGBTQ+
- **🔍 Smart Search**: Real-time book search with autocomplete
- **📚 Multiple Recommendation Tabs**: For You, Popular, By Author, Personalized
- **🎨 Modern UI**: Responsive design with book covers and ratings
- **🚫 Smart Filtering**: Excludes already-read books, strict genre matching

## 📁 Project Structure

```
├── app.py                    # Flask web application
├── data_loader.py            # Dataset loading (auto-downloads)
├── requirements.txt          # Dependencies
├── templates/                # HTML templates
│   ├── base.html            # Base template
│   ├── index.html           # Home page
│   ├── survey.html          # User survey
│   ├── book_detail.html     # Book details
│   └── search_results.html  # Search results
├── static/                   # CSS, JS, images
│   └── style.css            # Styling
└── recommenders/
    ├── popularity.py         # Trending/top-rated books
    ├── content_based.py      # Similar books by content
    ├── collaborative.py      # User-based recommendations
    └── hybrid.py             # Combined approach
```

## 📊 Dataset

Uses [goodbooks-10k](https://github.com/zygmuntz/goodbooks-10k):
- **10,000** books with metadata and cover images
- **~6 million** ratings from 53,424 users
- **34,252** unique genre tags
- **43** curated genre categories
- Rating scale: 1-5 stars

Dataset downloads automatically on first run.

### Genre Categories (43 Total)
**Fiction**: Fiction, Fantasy, Sci-Fi, Mystery, Crime & Detective, Thriller, Romance, Historical Fiction, Horror, Paranormal, Dystopian, Contemporary, Adventure, Western

**Age Groups**: Young Adult, New Adult, Children's, Middle Grade

**Non-Fiction**: Non-Fiction, Biography, Memoir, History, Self-Help, Psychology, Science, Philosophy, Religion & Spirituality, Business & Economics, Travel, Cookbooks & Food, Art & Photography

**Literary Forms**: Classics, Poetry, Short Stories, Essays, Drama & Plays, Humor, Satire

**Special Interest**: Comics & Manga, Fairy Tales & Folklore, LGBTQ+, Political

## 🎯 Key Improvements

| Enhancement | Description |
|-------------|-------------|
| Survey-driven personalization | No user IDs - natural survey-based profiling |
| Proxy user mapping | Maps survey responses to similar real users for CF |
| 43 genre categories | Expanded from 25 to 43 comprehensive genres |
| Strict genre filtering | Only shows books matching selected preferences |
| Modular architecture | Separated recommenders into distinct modules |
| Multiple algorithms | Combined popularity, content, collaborative filtering |
| Cold-start handling | Automatic fallback to popularity for new users |
| Auto-download | Dataset downloads from GitHub automatically |
| Modern Flask UI | Multi-tab interface with book covers and ratings |
| Session management | Persistent user preferences across pages |

## 🛠️ Technical Stack

- **Backend**: Flask (Python)
- **Frontend**: HTML, CSS, JavaScript
- **Data Processing**: Pandas, NumPy
- **ML Libraries**: Scikit-learn (TF-IDF, Cosine Similarity)
- **Dataset**: goodbooks-10k (auto-downloaded)

## 🚀 Advanced Features

### Recommendation Tabs
1. **For You**: Hybrid recommendations based on survey + CF
2. **Popular**: Top-rated books in selected genres
3. **By Author**: Explore books from favorite authors
4. **Personalized**: "Because you read..." recommendations

### Smart Filtering
- Excludes already-read books from all recommendations
- Strict genre matching (only shows books in selected categories)
- Proxy user mapping for accurate collaborative filtering
- Top 30 tags per book to avoid weak associations

## 📄 License
MIT License - See source repositories for their respective licenses.
