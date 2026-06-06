import os
os.environ["TORCH_COMPILE_DISABLE"] = "1"
import sqlite3
import chromadb
from backend.configurations.settings import settings
from backend.graph.orchestration import Workflow
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pathlib import Path

os.environ["GROQ_API_KEY"] = settings.GROQ_API_KEY

#os.environ["GEMINI_API_KEY"] = settings.GOOGLE_API_KEY

os.environ["TAVILY_API_KEY"] = settings.TAVILY_API_KEY
os.environ["tavily_key"] = settings.TAVILY_API_KEY

settings.DATABASE_DIR.mkdir(parents=True, exist_ok=True) # windows file vs folder error resolving
db_conn = sqlite3.connect(str(settings.SQLITE_PATH), check_same_thread=False)
schema_path = Path(__file__).resolve().parent / "schema.sql"
try: # if not pre existing ( i had error in new db )
    with open(schema_path, "r") as f:
        schema_script = f.read()
    db_conn.executescript(schema_script)
    db_conn.commit()
except Exception as schema_err:
    pass
chroma_client = chromadb.PersistentClient(path=str(settings.CHROMA_PATH))
chroma_collection = chroma_client.get_or_create_collection(name=settings.CHROMA_COLLECTION)
workflow = Workflow(db_conn=db_conn,chroma_client=chroma_client, chroma_collection=chroma_collection) # build workflow
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
    try:
        result = workflow.run(req.claim)
        report = result.get("verification_report",{})
        return {
           "claim": req.claim,
            "verdict": report.get("verdict"),
            "confidence": report.get("confidence"),
            "action": result.get("final_action"),
            "reasoning": report.get("reasoning","No explanation was provided by agents"),
            "sources": report.get("sources", []),
            "error": result.get("error")
        }
    except Exception as e:
        return {
            "claim": req.claim,
            "verdict": "ERROR",
            "confidence": 0.0,
            "action": "FLAG",
            "reasoning": f"An execution error stopped the workflow: {str(e)}",
            "sources": [],
            "error": str(e)
        }
@app.get("/health")
def health():
    return {"status": "ok"}