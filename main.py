import sqlite3
import chromadb
from backend.configurations.settings import settings
from backend.graph.orchestration import Workflow
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

settings.validate_env() # env validation
db_conn = sqlite3.connect(settings.DB_PATH, check_same_thread=False)
chroma_client = chromadb.PersistentClient(path=settings.CHROMA_PATH)
chroma_collection = chroma_client.get_or_create_collection(name=settings.CHROMA_COLLECTION_NAME)
workflow = Workflow(db_conn=db_conn, chroma_collection=chroma_collection) # build workflow
app = FastAPI(title="Sentinels of Truth")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class ClaimRequest(BaseModel):
    claim: str
@app.post("/verify")
def verify_claim(req: ClaimRequest):
    result = workflow.run(req.claim)
    return {
        "claim": req.claim,
        "verdict": result.get("verification_report", {}).get("verdict"),
        "confidence": result.get("verification_report", {}).get("confidence"),
        "action": result.get("final_action"),
        "error": result.get("error")
    }
@app.get("/health")
def health():
    return {"status": "ok"}