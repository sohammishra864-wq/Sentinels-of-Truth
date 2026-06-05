import logging
from pydantic import BaseModel, Field
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate

# MANY ERROR CAME HERE AS DB CONNECTION DISTANCE_LIST = 0 N ALL FOR LATER
logger = logging.getLogger(__name__)

SIMILARITY_THRESHOLD = 0.85
CONFIDENCE_THRESHOLD = 0.80

class ConflictSchema(BaseModel): # function for checking later to use i mean easy when needed
    is_contradictory: bool = Field(description="True if the incoming claim opposes the archived record")
    reasoning: str = Field(description="Brief explanation of the match or contradiction")

class LibrarianAgent:
    def __init__(self, db_conn, chroma_collection):
        self.db = db_conn
        self.chroma = chroma_collection
        self.llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)

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

        results = self.chroma.query(query_texts=[claim], n_results=3)
        if results and results.get('distances') and results['distances'][0]:
            similarity = 1 - results['distances'][0][0] # error occured so this thing
            if similarity >= SIMILARITY_THRESHOLD: # the list was 0 so error came
                match_id = results['ids'][0][0] # so thats why i had to do the try except
                cursor = self.db.cursor()
                try:
                    cursor.execute("SELECT claim_text, verdict FROM claims WHERE claim_id = ?", (match_id,))
                    archive_record = cursor.fetchone()
                finally:
                    cursor.close()
                if archive_record:
                    prompt = ChatPromptTemplate.from_messages([
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
                            "new_verdict": report.get("Verdict", "UNKNOWN") # if missing
                        })
                    except Exception as e:
                        logger.error(f"LLM chain failed during conflict check: {e}")
                        return {"action": "FLAG", "Reason": f"Conflict check failed: {str(e)}"}
                    if analysis.is_contradictory:
                        return {
                            "action": "FLAG",
                            "reason": f"contradiction found: {analysis.reasoning}"
                        }
                    return {
                        "action": "DISCARD",
                        "reason": "Semantically same existing DB Record"
                    }
        confidence = report.get("confidence", 0.0)
        if confidence >= CONFIDENCE_THRESHOLD:
            return {
                "action": "INSERT",
                "reason": "Valid new claim"
            }
        return {
            "action": "FLAG",
            "reason": f"Low confidence score: {confidence}"
        }