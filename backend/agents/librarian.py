import logging
from pydantic import BaseModel, Field
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate

# MANY ERROR CAME HERE AS DB CONNECTION DISTANCE_LIST = 0 N ALL FOR LATER
logger = logging.getLogger(__name__)

SIMILARITY_THRESHOLD = 0.85
CONFIDENCE_THRESHOLD = 0.80

class ConflictSchema(BaseModel): # function for checking later to use i mean easy when needed
    is_contradictory: bool = Field(description="True if the incoming claim opposes the archived record")
    reasoning: str = Field(description="Brief explanation of the match or contradiction")

class LibrarianAgent:
    def __init__(self, db_conn, chroma_manager):
        self.db = db_conn
        self.chroma = chroma_manager
        self.llm = ChatGroq(model="llama-3.1-8b-instant", temperature=0)


    # duplicate check
    def check(self, claim: str, report: dict) -> dict:
        if not claim or not report:
            raise ValueError("Missing claim text or report payload")
        cursor = self.db.cursor()
        try:
            cursor.execute("SELECT claim_id FROM claims WHERE claim_text = ?", (claim,))
            if cursor.fetchone():
                return {
                    "action": "DISCARD",
                    "reason": "Exact claim string already exists in DB"
                }
        finally:
            cursor.close()

        results = self.chroma.search_similar(claim, n_results=3)
        if results:
            similarity = results[0]["similarity"]
            if similarity >= SIMILARITY_THRESHOLD: # better one for 0 list
                match_id = results[0]["claim_id"] # so thats why i had to do the try except
                archive_record = None
                cursor = self.db.cursor()
                try:
                    if str(match_id).isdigit():
                        cursor.execute("SELECT claim_text, verdict FROM claims WHERE claim_id = ?", (int(match_id),))
                        archive_record = cursor.fetchone()
                    else:
                        cursor.execute("SELECT claim_text, verdict FROM claims WHERE claim_text = ?", (claim,))
                        archive_record = cursor.fetchone()
                finally:
                    cursor.close()
                if archive_record:
                    prompt = ChatPromptTemplate.from_messages([ # from llm
                        ("system", (
                           "You are an AI data auditor compare the new claim against the old archive record to spot contradictions\n\n"
                            "Archive: {old_text} (Verdict: {old_verdict})\n"
                            "Incoming: {new_text} (Verdict: {new_verdict})"
                        )),
                        ("human", "Is there a factual contradiction?")
                    ])

                    structured_llm = self.llm.with_structured_output(ConflictSchema)
                    chain = prompt | structured_llm

                    try:
                        analysis = chain.invoke({
                            "old_text": archive_record[0],
                            "old_verdict": archive_record[1],
                            "new_text": claim,
                            "new_verdict": report.get("verdict", "UNKNOWN") # if missing
                        })
                    except Exception as e:
                        logger.error(f"LLM chain failed during conflict check:{e}")
                        return {"action": "FLAG", "Reason": f"Conflict check failed: {str(e)}"}
                    if analysis.is_contradictory:
                        return {
                            "action": "FLAG",
                            "reason": f"contradiction found: {analysis.reasoning}",
                            "conflicting_id": int(match_id) if str(match_id).isdigit() else None
                        }
                    return { # not same as duplicate though
                        "action": "DISCARD",
                        "reason": "Semantically same existing DB Record"
                    }
        verdict = report.get("verdict", "UNCERTAIN").upper() # check before commit
        confidence = report.get("confidence", 0.0)
        if verdict == "REAL" and confidence >= CONFIDENCE_THRESHOLD:
            return { #earlier in both case inserted
                "action": "INSERT",
                "reason": "Valid new claim"
            }
        return { # if claim is fake
            "action": "FLAG",
            "reason": f"Low confidence score: {confidence}"
        }