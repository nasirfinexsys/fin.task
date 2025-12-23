# 📄 Intelligent PDF Document Management System

An AI-powered PDF document management system with semantic search and Q&A capabilities, built with Django, Celery, and Google Gemini AI.

## 🌟 Features

- **📤 PDF Upload & Processing**
  - Automatic text extraction using Gemini AI
  - Fallback to pypdf and OCR for maximum reliability
  - Support for both digital and scanned PDFs

- **🔍 Dual Search System**
  - **Full-Text Search**: Fast keyword-based search with PostgreSQL GIN indexes
  - **Semantic Search**: AI-powered understanding of meaning, not just keywords

- **💬 Q&A System (RAG)**
  - Ask natural language questions about your documents
  - AI generates accurate answers based on document content
  - Shows source documents for verification

- **⚡ Background Processing**
  - Non-blocking uploads with Celery task queue
  - Real-time status updates
  - Efficient handling of large documents

- **🔐 Authentication**
  - Email/password login
  - Google OAuth integration
  - User-specific document isolation

## 🏗️ Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Django    │────▶│    Redis    │────▶│   Celery    │
│  (Web App)  │     │  (Broker)   │     │  (Worker)   │
└─────────────┘     └─────────────┘     └─────────────┘
       │                                        │
       │                                        │
       ▼                                        ▼
┌─────────────┐                        ┌─────────────┐
│ PostgreSQL  │                        │ Gemini API  │
│  (NeonDB)   │                        │   (AI)      │
└─────────────┘                        └─────────────┘
```

## 🚀 Tech Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Backend** | Django 6.0 | Web framework |
| **Database** | PostgreSQL (NeonDB) | Data storage with vector support |
| **Task Queue** | Celery 5.6 + Redis | Background processing |
| **AI** | Google Gemini API | Text extraction, embeddings, Q&A |
| **Storage** | AWS S3 / Local | File storage |
| **Container** | Docker + Docker Compose | Deployment |
| **Auth** | Django Allauth | Authentication + OAuth |

## 📋 Prerequisites

- **Docker & Docker Compose** (recommended) OR
- **Python 3.12+** (for local development)
- **PostgreSQL 13+** with pgvector extension
- **Google Gemini API Key** ([Get one here](https://makersuite.google.com/app/apikey))

## ⚙️ Installation

### Option 1: Docker (Recommended)

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd fin.task
   ```

2. **Create `.env` file**
   ```bash
   cp .env.example .env
   ```
   
   Edit `.env` and add:
   ```bash
   # Django
   SECRET_KEY=your-secret-key-here
   DEBUG=True
   ALLOWED_HOSTS=localhost,127.0.0.1
   
   # Database (NeonDB)
   DATABASE_URL=postgresql://user:password@host:5432/database
   
   # Gemini API
   GEMINI_API_KEY=your-gemini-api-key-here
   
   # Google OAuth (optional)
   GOOGLE_OAUTH_CLIENT_ID=your-client-id
   GOOGLE_OAUTH_CLIENT_SECRET=your-client-secret
   
   # AWS S3 (optional, for production)
   AWS_ACCESS_KEY_ID=your-aws-key
   AWS_SECRET_ACCESS_KEY=your-aws-secret
   AWS_STORAGE_BUCKET_NAME=your-bucket-name
   AWS_S3_REGION_NAME=us-east-1
   ```

3. **Start the application**
   ```bash
   docker-compose up --build
   ```

4. **Access the application**
   - Web interface: http://localhost:8000
   - Admin panel: http://localhost:8000/admin

### Option 2: Local Development

1. **Create virtual environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your credentials
   ```

4. **Run migrations**
   ```bash
   python manage.py migrate
   ```

5. **Create superuser**
   ```bash
   python manage.py createsuperuser
   ```

6. **Start services** (3 terminals)
   
   Terminal 1 - Django:
   ```bash
   python manage.py runserver
   ```
   
   Terminal 2 - Redis:
   ```bash
   redis-server
   ```
   
   Terminal 3 - Celery:
   ```bash
   celery -A config worker --loglevel=info
   ```

## 📖 Usage

### 1. Upload Documents

1. Navigate to http://localhost:8000/upload/
2. Enter document title
3. Select PDF file (max 50MB)
4. Click upload

**What happens behind the scenes:**
- PDF saved to storage
- Celery task triggered for background processing
- Gemini AI extracts text (with pypdf/OCR fallback)
- Text split into chunks
- Embeddings generated for semantic search
- Document ready for search and Q&A

### 2. Search Documents

**Full-Text Search:**
```
http://localhost:8000/documents/?search=revenue
```
- Fast keyword-based search
- Uses PostgreSQL GIN indexes

**Semantic Search:**
```
http://localhost:8000/search/?q=financial performance
```
- AI-powered understanding
- Finds related concepts (e.g., "profit", "revenue", "earnings")

### 3. Ask Questions (Q&A)

```
http://localhost:8000/qna/?q=What was the company's revenue in 2024?
```

The system:
1. Finds relevant document chunks using semantic search
2. Sends context to Gemini AI
3. Generates accurate answer
4. Shows source documents

## 🗂️ Project Structure

```
fin.task/
├── apps/
│   └── documents/              # Main app
│       ├── models.py           # Document & DocumentChunk models
│       ├── views.py            # Web views & API endpoints
│       ├── tasks.py            # Celery background tasks
│       ├── services.py         # AI/embedding functions
│       ├── urls.py             # URL routing
│       └── migrations/         # Database migrations
│
├── config/                     # Project settings
│   ├── settings.py             # Main configuration
│   ├── urls.py                 # Root URL routing
│   ├── celery.py               # Celery configuration
│   └── wsgi.py                 # WSGI server config
│
├── templates/                  # HTML templates
│   ├── dashboard.html
│   ├── upload.html
│   ├── semantic_search.html
│   └── qna.html
│
├── media/                      # Uploaded files (local dev)
├── docker-compose.yml          # Docker services configuration
├── Dockerfile                  # Docker image definition
├── requirements.txt            # Python dependencies
├── manage.py                   # Django CLI
└── README.md                   # This file
```

## 🔧 Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `SECRET_KEY` | Django secret key | Yes |
| `DEBUG` | Debug mode (True/False) | Yes |
| `DATABASE_URL` | PostgreSQL connection string | Yes |
| `GEMINI_API_KEY` | Google Gemini API key | Yes |
| `GOOGLE_OAUTH_CLIENT_ID` | Google OAuth client ID | No |
| `GOOGLE_OAUTH_CLIENT_SECRET` | Google OAuth secret | No |
| `AWS_ACCESS_KEY_ID` | AWS S3 access key | No |
| `AWS_SECRET_ACCESS_KEY` | AWS S3 secret key | No |
| `AWS_STORAGE_BUCKET_NAME` | S3 bucket name | No |

### Database Setup (NeonDB)

1. Create account at [Neon.tech](https://neon.tech)
2. Create new project
3. Enable pgvector extension:
   ```sql
   CREATE EXTENSION IF NOT EXISTS vector;
   ```
4. Copy connection string to `DATABASE_URL`

See [NEONDB_SETUP.md](NEONDB_SETUP.md) for detailed instructions.

### Google OAuth Setup (Optional)

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create OAuth 2.0 credentials
3. Add authorized redirect URI: `http://localhost:8000/accounts/google/login/callback/`
4. Add credentials to `.env`

See [GOOGLE_LOGIN_SETUP.md](GOOGLE_LOGIN_SETUP.md) for details.

## 🧪 Testing

### Upload a test document
```bash
# Via web interface
Open http://localhost:8000/upload/

# Via API
curl -X POST http://localhost:8000/api/documents/ \
  -H "Authorization: Token <your-token>" \
  -F "title=Test Document" \
  -F "file=@path/to/document.pdf"
```

### Check processing status
```bash
# View logs
docker-compose logs -f worker

# Or check database
python manage.py shell
>>> from apps.documents.models import Document
>>> doc = Document.objects.last()
>>> print(doc.status, doc.embedding_status)
```

## 📊 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/documents/` | GET | List user's documents |
| `/api/documents/` | POST | Upload new document |
| `/api/documents/<id>/` | GET | Get document details |
| `/api/documents/<id>/` | DELETE | Delete document |
| `/api/qna/` | POST | Ask question (Q&A) |

## 🐛 Troubleshooting

### Issue: Gemini extraction fails
**Solution:** Check GEMINI_API_KEY in `.env` file
```bash
docker-compose logs worker | grep "Gemini"
```

### Issue: Embeddings not generating
**Solution:** Ensure Celery worker is running
```bash
docker-compose ps
# Should show: fintask-worker-1 running
```

### Issue: Port 8000 already in use
**Solution:** Kill existing process
```bash
lsof -ti:8000 | xargs kill -9
```

### Issue: Database connection fails
**Solution:** Check DATABASE_URL format
```
postgresql://user:password@host:5432/database
```

## 📚 Additional Documentation

- [Embedding Setup Guide](EMBEDDING_SETUP.md)
- [Gemini Extraction Details](GEMINI_EXTRACTION.md)
- [Search Vector Explanation](SEARCH_VECTOR_EXPLANATION.md)
- [NeonDB Setup](NEONDB_SETUP.md)
- [Google Login Setup](GOOGLE_LOGIN_SETUP.md)

## 🔄 Workflow Overview

```
1. User uploads PDF
   ↓
2. Save to database + storage
   ↓
3. Trigger background task
   ↓
4. Extract text (Gemini → pypdf → OCR)
   ↓
5. Generate embeddings
   ↓
6. Document ready for:
   - Full-text search
   - Semantic search
   - Q&A
```


