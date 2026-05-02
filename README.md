# 🚀 CogniVault - AI Document Intelligence RAG System

A production-ready **Retrieval-Augmented Generation (RAG)** system that lets you upload documents (PDFs, TXT, Markdown) and ask questions using natural language to get instant, cited answers.

---

## ✨ Features

### 💬 **Smart Document Q&A**
- Upload PDFs, TXT, or Markdown files
- Ask questions in **any language** (English, Hindi, Urdu, etc.)
- Get **instant answers with source citations**
- Multi-language support with automatic translation

### 📁 **Document Management**
- Upload unlimited documents (paid plans)
- Automatic indexing to Qdrant vector database
- File tracking with MD5 hash deduplication
- Delete files instantly - vectors removed from DB

### 🔒 **Privacy & Performance**
- Local Qdrant vector storage (no cloud required)
- SQLite database for file metadata tracking
- Chunking prevents hallucinations (500-char chunks)
- Cosine similarity for accurate retrieval

### 💎 **Flexible Pricing**
- **Free Plan:** 5 chats/month
- **Professional:** ₹9,999/month - Unlimited everything

---

## 🛠️ Installation

### Quick Start (Local)

#### Prerequisites
```bash
Python 3.10+
pip or uv
OpenAI API Key
```

#### Setup
```bash
# 1. Clone/Extract
cd RAG

# 2. Create .env file
cp .env.example .env
# Edit .env with your OPENAI_API_KEY

# 3. Install dependencies
pip install -r requirements.txt
# OR with uv:
uv pip install -r requirements.txt

# 4. Run the application
python app.py
```

Server starts at: **http://127.0.0.1:8000**

---

## 🐳 Docker Deployment

### Prerequisites
```bash
Docker 20.10+
Docker Compose 2.0+
```

### Setup with Docker

```bash
# 1. Setup environment
cp .env.example .env
# Edit .env with your OPENAI_API_KEY

# 2. Build and start
docker-compose up -d

# 3. View logs
docker-compose logs -f app

# 4. Access application
# Frontend: http://localhost:8000
# Vector DB API: http://localhost:6333
```

### Docker Services

```yaml
- app: CogniVault API + Frontend (port 8000)
- vector-db: Qdrant Vector Database (port 6333)
```

### Persistent Storage
- `./pdfs/` - Uploaded documents
- `./qdrant_local_data/` - Vector embeddings
- `./pdf_tracker.db` - File metadata + hash tracking

---

## 📊 System Architecture

```
┌─────────────────────────────────────┐
│       Frontend (HTML/JS)             │
│   - Beautiful UI                      │
│   - File upload                       │
│   - Chat interface                    │
└────────────┬────────────────────────┘
             │
             ↓
┌─────────────────────────────────────┐
│      FastAPI Backend (main.py)       │
│  - /upload    → Process & index      │
│  - /ask       → RAG retrieval        │
│  - /files     → List documents       │
│  - /delete    → Remove from DB       │
└────────────┬────────────────────────┘
             │
       ┌─────┴──────┬──────────┐
       ↓            ↓          ↓
   ┌────────┐  ┌────────┐  ┌──────────┐
   │pdf_    │  │Qdrant  │  │SQLite DB │
   │loader  │  │Vector  │  │pdf_     │
   │(PyPDF) │  │DB      │  │tracker  │
   └────────┘  └────────┘  └──────────┘
       ↓            ↓          ↓
   [PDFs]     [Embeddings]   [Metadata]
```

---

## 🔌 API Endpoints

### Chat with Documents
```http
POST /ask
Content-Type: application/json

{
  "query": "What is RAG?",
  "file_name": null  # null = search all files
}

Response:
{
  "answer": "RAG combines retrieval with generation...",
  "language": "English",
  "sources": ["RAG.PDF - Page 2", "RAG.PDF - Page 5"]
}
```

### Upload File
```http
POST /upload
Content-Type: multipart/form-data

file: <PDF/TXT/MD file>

Response:
{
  "message": "Uploaded: document.pdf — 247 chunks"
}
```

### List Files
```http
GET /files

Response:
{
  "files": ["RAG.PDF", "document.pdf", "guide.txt"]
}
```

### Delete File
```http
DELETE /delete/RAG.PDF

Response:
{
  "message": "Deleted: RAG.PDF"
}
```

### Health Check
```http
GET /health

Response:
{
  "status": "ok"
}
```

---

## 📝 Configuration

### Environment Variables (.env)

```env
# Required
OPENAI_API_KEY=sk-...

# Optional (for cloud Qdrant)
QDRANT_URL=
QDRANT_API_KEY=

# Server
API_HOST=127.0.0.1
API_PORT=8000

# Frontend CORS
FRONTEND_ORIGINS=http://localhost:3000
```

### File Locations

| Item | Path |
|------|------|
| PDFs | `./pdfs/` |
| Vector DB | `./qdrant_local_data/` |
| File Metadata | `./pdf_tracker.db` |
| HTML Frontend | `./market_frontend.html` |
| Configuration | `./.env` |

---

## 🎯 Usage Examples

### In Browser
1. Open http://127.0.0.1:8000
2. Click "Open Workspace"
3. Go to "My Files" → Upload PDF
4. Go to "Chat with Docs" → Ask questions
5. Get instant answers with citations!

### Programmatically
```python
import requests

# Send query
response = requests.post("http://127.0.0.1:8000/ask", json={
    "query": "What are the main topics?",
    "file_name": None
})

result = response.json()
print(result["answer"])
print(result["sources"])
```

---

## 🔧 Technical Details

### Core Components

| Component | Purpose |
|-----------|---------|
| `main.py` | FastAPI server + routes |
| `pdf_loader.py` | Document processing |
| `retreive.py` | RAG retrieval logic |
| `market_frontend.html` | Web interface |
| `docker-compose.yml` | Container orchestration |

### Technologies

- **Framework:** FastAPI
- **Vector DB:** Qdrant (local or cloud)
- **Embeddings:** OpenAI text-embedding-3-large
- **LLM:** OpenAI GPT-4.1-mini
- **Database:** SQLite (metadata) + Qdrant (vectors)
- **Frontend:** Vanilla HTML/CSS/JS

### Processing Pipeline

```
Document → Chunks (500 chars) → Embeddings → Qdrant
Query → Breakdown (3 sub-queries) → Search → Top-6 chunks
Context + Query → GPT-4.1-mini → Answer with citations
```

---

## 📊 Pricing Plans

### Free Plan
- 5 chats per month
- Upload PDF, TXT, Markdown files
- Source citations

### Professional Plan (₹9,999/month)
- ✓ Unlimited chats
- ✓ Unlimited documents
- ✓ Priority AI response
- ✓ Priority support

---

## 🐛 Troubleshooting

### Server won't start
```bash
# Kill existing processes
pkill -f "python app.py"

# Clear locks
rm -rf qdrant_local_data/.lock

# Restart
python app.py
```

### Files not uploading
- Check `./pdfs/` directory exists
- Verify OPENAI_API_KEY is set
- Check OpenAI API quota

### Qdrant errors
```bash
# Docker - restart vector DB
docker-compose restart vector-db

# Local - remove lock file
rm qdrant_local_data/.lock
```

### No AI responses
- Verify OPENAI_API_KEY in `.env`
- Check OpenAI API is accessible
- Upload at least one document first

---

## 📈 Performance Tips

1. **Chunk Size:** Default 500 chars works best
2. **Overlap:** 100 chars helps context flow
3. **Top-K:** 6 chunks balances quality vs tokens
4. **Language:** Auto-detect + translation improves accuracy

---

## 🔐 Security Notes

- Store API keys in `.env` (never commit!)
- Use CORS carefully in production
- Consider rate limiting for public APIs
- Enable authentication for deployment

---

## 📚 Resources

- [FastAPI Docs](https://fastapi.tiangolo.com/)
- [Qdrant Docs](https://qdrant.tech/documentation/)
- [LangChain Docs](https://langchain.readthedocs.io/)
- [OpenAI API](https://platform.openai.com/docs/)

---

## 📄 File Structure

```
RAG/
├── main.py                 # FastAPI server
├── app.py                  # Entry point
├── pdf_loader.py           # Document processing
├── retreive.py             # RAG retrieval
├── market_frontend.html    # Web UI
├── docker-compose.yml      # Container setup
├── Dockerfile              # Image build
├── pyproject.toml          # Dependencies
├── .env.example            # Config template
├── pdf_tracker.db          # SQLite metadata
├── pdfs/                   # Uploaded documents
└── qdrant_local_data/      # Vector storage
```

---

## 🤝 Contributing

Found a bug? Want to add features?

1. Create an issue
2. Fork and make changes
3. Test thoroughly
4. Submit PR

---

## 📞 Support

For issues or questions:
- Check logs: `docker-compose logs app`
- Review `.env` configuration
- Verify OPENAI_API_KEY validity
- Check database permissions

---

## 📄 License

Built with ❤️ for document intelligence.

---

**Happy questioning! 🚀**
