import ast
import hashlib
import os
import shutil
from concurrent.futures import ThreadPoolExecutor
from itertools import chain
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth.dependencies import check_active_subscription
from auth.router import router as auth_router
from dependencies.database import engine, get_db
from models import Base, Document, User

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
PDFS_DIR = BASE_DIR / "pdfs"
QDRANT_DIR = BASE_DIR / "qdrant_local_data"
COLLECTION_NAME = "learning-rag"

PDFS_DIR.mkdir(exist_ok=True)
QDRANT_DIR.mkdir(exist_ok=True)

# Initialize database tables on startup (can be done once safely)
try:
    Base.metadata.create_all(bind=engine)
except Exception as e:
    print(f"Warning: Database initialization failed: {e}")

# Lazy-loaded to avoid blocking imports
embedding_model = None
qdrant_client = None
vector_store = None
text_splitter = None
openai_client = None


def init_ai_components():
    """Initialize OpenAI and Qdrant components"""
    global embedding_model, qdrant_client, vector_store, text_splitter, openai_client

    if embedding_model is not None:
        return  # Already initialized

    print("Initializing AI components...")

    # Lazy import to avoid hanging on startup
    from openai import OpenAI
    from langchain_openai import OpenAIEmbeddings
    from langchain_qdrant import QdrantVectorStore
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    from qdrant_client import QdrantClient
    from qdrant_client.models import (
        Distance,
        Filter,
        FieldCondition,
        MatchValue,
        VectorParams,
    )

    embedding_model = OpenAIEmbeddings(model="text-embedding-3-large")
    qdrant_client = QdrantClient(path=str(QDRANT_DIR))

    existing = [c.name for c in qdrant_client.get_collections().collections]
    if COLLECTION_NAME not in existing:
        qdrant_client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=3072, distance=Distance.COSINE),
        )

    vector_store = QdrantVectorStore(
        client=qdrant_client,
        collection_name=COLLECTION_NAME,
        embedding=embedding_model,
    )
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=100)
    openai_client = OpenAI()
    print("✓ AI components initialized")


app = FastAPI(title="CogniVault RAG API", version="2.0.0")
app.include_router(auth_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class AskRequest(BaseModel):
    query: str
    file_name: str | None = None


def get_hash(path: Path) -> str:
    digest = hashlib.md5()
    with open(path, "rb") as file_obj:
        for chunk in iter(lambda: file_obj.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def detect_language(query: str) -> str:
    response = openai_client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {
                "role": "system",
                "content": "Detect the language and return only language name in English.",
            },
            {"role": "user", "content": query},
        ],
        temperature=0,
    )
    return response.choices[0].message.content.strip()


def breakdown_query(query: str) -> list[str]:
    response = openai_client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {
                "role": "system",
                "content": "Break into max 3 concise English search sub-queries. Return Python list only.",
            },
            {"role": "user", "content": query},
        ],
        temperature=0.1,
    )
    try:
        parsed = ast.literal_eval(response.choices[0].message.content.strip())
        if isinstance(parsed, list) and parsed:
            return [str(item) for item in parsed[:3]]
    except (SyntaxError, ValueError):
        pass
    return [query]


def retrieve_chunks(query: str, vector_file_id: str | None = None):
    if vector_file_id:
        return vector_store.similarity_search(
            query,
            k=6,
            filter=Filter(
                must=[
                    FieldCondition(
                        key="metadata.file_id", match=MatchValue(value=vector_file_id)
                    )
                ]
            ),
        )
    return vector_store.similarity_search(query, k=6)


def _vector_file_id(user_id: str, file_name: str) -> str:
    return f"{user_id}:{file_name}"


@app.on_event("shutdown")
async def shutdown_event():
    if qdrant_client is not None:
        qdrant_client.close()


@app.get("/")
def root():
    from fastapi.responses import RedirectResponse

    return RedirectResponse(url="/app")


@app.get("/app", include_in_schema=False)
def serve_frontend():
    """Serve the frontend application"""
    frontend_file = BASE_DIR / "market_frontend.html"
    if frontend_file.exists():
        return FileResponse(frontend_file)
    raise HTTPException(status_code=404, detail="Frontend not found")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/documents")
def list_documents(
    current_user: User = Depends(check_active_subscription),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(Document)
        .filter(Document.user_id == current_user.id)
        .order_by(Document.created_at.desc())
        .all()
    )
    return {
        "documents": [
            {
                "id": row.id,
                "file_name": row.file_name,
                "chunks_count": row.chunks_count,
                "created_at": row.created_at,
            }
            for row in rows
        ]
    }


@app.get("/files")
def list_files(
    current_user: User = Depends(check_active_subscription),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(Document.file_name)
        .filter(Document.user_id == current_user.id)
        .order_by(Document.created_at.desc())
        .all()
    )
    return {"files": [row[0] for row in rows]}


@app.post("/upload")
async def upload(
    file: UploadFile = File(...),
    current_user: User = Depends(check_active_subscription),
    db: Session = Depends(get_db),
):
    init_ai_components()  # Initialize AI components on first use

    # Lazy imports for PDF processing
    from langchain_community.document_loaders import PyPDFLoader
    from qdrant_client.models import Filter, FieldCondition, MatchValue

    if not file.filename:
        raise HTTPException(status_code=400, detail="Invalid file name")
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400, detail="Only PDF upload is currently supported"
        )

    user_dir = PDFS_DIR / current_user.id
    user_dir.mkdir(parents=True, exist_ok=True)
    target_path = user_dir / file.filename
    with open(target_path, "wb") as out_file:
        shutil.copyfileobj(file.file, out_file)

    file_hash = get_hash(target_path)
    vector_file_id = _vector_file_id(current_user.id, file.filename)

    existing_doc = (
        db.query(Document)
        .filter(
            Document.user_id == current_user.id, Document.file_name == file.filename
        )
        .first()
    )
    if existing_doc:
        qdrant_client.delete(
            collection_name=COLLECTION_NAME,
            points_selector=Filter(
                must=[
                    FieldCondition(
                        key="metadata.file_id",
                        match=MatchValue(value=existing_doc.vector_file_id),
                    )
                ]
            ),
        )

    docs = PyPDFLoader(str(target_path)).load()
    chunks = text_splitter.split_documents(docs)
    for chunk in chunks:
        chunk.metadata["file_id"] = vector_file_id
        chunk.metadata["source"] = file.filename
        chunk.metadata["user_id"] = current_user.id
    vector_store.add_documents(chunks)

    if not existing_doc:
        existing_doc = Document(
            user_id=current_user.id,
            file_name=file.filename,
            file_hash=file_hash,
            vector_file_id=vector_file_id,
            chunks_count=len(chunks),
        )
        db.add(existing_doc)
    else:
        existing_doc.file_hash = file_hash
        existing_doc.vector_file_id = vector_file_id
        existing_doc.chunks_count = len(chunks)
    db.commit()

    return {"message": f"Uploaded: {file.filename}", "chunks": len(chunks)}


@app.delete("/delete-document/{file_name}")
def delete_document(
    file_name: str,
    current_user: User = Depends(check_active_subscription),
    db: Session = Depends(get_db),
):
    row = (
        db.query(Document)
        .filter(Document.user_id == current_user.id, Document.file_name == file_name)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="File not found")

    qdrant_client.delete(
        collection_name=COLLECTION_NAME,
        points_selector=Filter(
            must=[
                FieldCondition(
                    key="metadata.file_id", match=MatchValue(value=row.vector_file_id)
                )
            ]
        ),
    )

    user_file = PDFS_DIR / current_user.id / file_name
    if user_file.exists():
        user_file.unlink()

    db.delete(row)
    db.commit()
    return {"message": f"Deleted: {file_name}"}


@app.delete("/delete/{file_name}")
def delete_document_alias(
    file_name: str,
    current_user: User = Depends(check_active_subscription),
    db: Session = Depends(get_db),
):
    return delete_document(file_name=file_name, current_user=current_user, db=db)


def _run_answer(req: AskRequest, current_user: User, db: Session):
    init_ai_components()  # Initialize AI components on first use

    lang = detect_language(req.query)
    sub_queries = breakdown_query(req.query)

    vector_file_id = None
    if req.file_name:
        row = (
            db.query(Document)
            .filter(
                Document.user_id == current_user.id, Document.file_name == req.file_name
            )
            .first()
        )
        if not row:
            raise HTTPException(
                status_code=404, detail="Requested file not found for this user"
            )
        vector_file_id = row.vector_file_id

    with ThreadPoolExecutor() as executor:
        all_chunks = list(
            executor.map(lambda q: retrieve_chunks(q, vector_file_id), sub_queries)
        )

    unique_chunks = list(
        {doc.page_content: doc for doc in chain.from_iterable(all_chunks)}.values()
    )
    if not unique_chunks:
        return {
            "answer": "This information is not available in the provided documents.",
            "language": lang,
            "sources": [],
        }

    context = "\n\n".join(
        [
            f"[Source: {doc.metadata.get('source', 'unknown')} | Page: {doc.metadata.get('page', '?')}]\n{doc.page_content}"
            for doc in unique_chunks
        ]
    )
    system_prompt = (
        f"You are an expert document analyst. Reply in {lang} using Roman script. "
        "Answer only from context and cite source tags. "
        f"Context:\n{context}"
    )
    answer = openai_client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": req.query},
        ],
        temperature=0.1,
        max_tokens=1500,
    )
    return {
        "answer": answer.choices[0].message.content,
        "language": lang,
        "sources": list(
            {
                f"{doc.metadata.get('source', '?')} - Page {doc.metadata.get('page', '?')}"
                for doc in unique_chunks
            }
        ),
    }


@app.post("/ask")
def ask(
    req: AskRequest,
    current_user: User = Depends(check_active_subscription),
    db: Session = Depends(get_db),
):
    return _run_answer(req, current_user, db)


@app.post("/chat")
def chat(
    req: AskRequest,
    current_user: User = Depends(check_active_subscription),
    db: Session = Depends(get_db),
):
    return _run_answer(req, current_user, db)


@app.post("/query")
def query(
    req: AskRequest,
    current_user: User = Depends(check_active_subscription),
    db: Session = Depends(get_db),
):
    return _run_answer(req, current_user, db)
