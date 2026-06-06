from typing import TypedDict
import os
from backend.agents.scout import ScoutAgent
from backend.agents.librarian import LibrarianAgent
from langgraph.graph import StateGraph, END
import logging
from backend.database.sqlite_manager import SQLite_manager
from backend.database.chromadb_manager import Chromamanager
from sentence_transformers import SentenceTransformer
from backend.configurations.settings import settings
logger = logging.getLogger(__name__)

class GraphState(TypedDict):
    claim: str
    verification_report: dict
    final_action: str
    error: str

class Workflow:
    def __init__(self, db_conn,chroma_client, chroma_collection):
        tavily_key = os.getenv("TAVILY_API_KEY", "")
        if not tavily_key:
            logger.warning("Tavily API key is missing from environment variables!")
            # scout librarian error fixed now api one and db
        self.sql_manager = SQLite_manager(db_conn) # missed to connect db with worlflow
        self.embedding_model = SentenceTransformer(settings.EMBEDDING_MODEL)
        # error came here
        self.chroma_manager = Chromamanager(
            client=chroma_client,
            collection_name=settings.CHROMA_COLLECTION,
            embedding_model=self.embedding_model
        )
        self.scout = ScoutAgent(tavily_api_key=tavily_key)
        self.librarian = LibrarianAgent(db_conn=db_conn, chroma_manager=self.chroma_manager)
        self.graph = self._build_graph()

    def _scout_node(self, state: GraphState) -> dict: # just to be safe incase i use
        claim_text = state.get("claim", "").strip()
        if not claim_text:
            return {"error": "Empty claim text submitted", "final_action": "FLAG"}
        try:
            report = self.scout.investigate(claim_text)
            return {"verification_report": report}
        except Exception as e:
            logger.error(f"Scout node crashed: {e}")
            return {"error": f"Scout pipeline failed: {str(e)}", "final_action": "FLAG"}

    def _librarian_node(self, state: GraphState) -> dict:
        if state.get("error"):
            return {
                "error": state.get("error"),
                "final_action": state.get("final_action", "FLAG")
            }
        claim_text = state.get("claim")
        report_data = state.get("verification_report")
        action = "FLAG"
        try: ##### for safety and connection previously problem #####
            decision = self.librarian.check(claim_text,report_data)
            if decision and isinstance(decision, dict):
                action = decision.get("action", "FLAG")

            if action == "INSERT" and report_data:
                logger.info(f"Inserting claim {claim_text}")
                raw_sources = report_data.get("evidence") or report_data.get("sources") or []
                if not isinstance(raw_sources, list):
                    raw_sources = [str(raw_sources)] if raw_sources else []
                new_claim_id =  self.sql_manager.insert_claim(
                    text=claim_text,
                    verdict=report_data.get("verdict", "UNCERTAIN"),
                    confidence=report_data.get("confidence", 0.0),
                    sources=raw_sources
                )
                logger.info(f"Syncing new claim to ChromaDB with ID: {new_claim_id}")
                self.chroma_manager.add_claim( # knowledge sync to vdb
                    claim_id=str(new_claim_id),
                    claim_text=claim_text,
                    metadata={"verdict": report_data.get("verdict", "UNCERTAIN")}
                )
            elif action == "FLAG":
                conflicting_id = decision.get("conflicting_id") if decision else None
                if conflicting_id is not None:
                    logger.info(f"Logging flagged conflict for claim: {claim_text} against match ID: {conflicting_id}")
                    self.sql_manager.insert_conflict(text=claim_text, existing_id=conflicting_id)
                else:
                    logger.info(f"Claim flagged for low confidence, no conflict record created: {claim_text}")
            elif action == "DISCARD":
                logger.info(f"Duplicate content identified for: '{claim_text}'. System dropped entry safely.")
                if not report_data:
                    report_data = {}
                report_data["reasoning"] = decision.get("reason","This exact claim or an identical variation already exists in the system records.")
                report_data["verdict"] = "REAL"
                report_data["confidence"] = 1.0
            return{
                "final_action": action,
                "verification_report": report_data
            }
        except Exception as e:
            logger.error(f"Librarian node crashed: {e}")
            return {"error": f"Librarian pipeline failed: {str(e)}", "final_action": "FLAG", "verification_report": report_data}

    def _build_graph(self):
        build = StateGraph(GraphState)
        build.add_node("scout_agent", self._scout_node) # execution node add
        build.add_node("librarian_agent", self._librarian_node)
        build.set_entry_point("scout_agent") # agents workflow order nodes
        build.add_edge("scout_agent", "librarian_agent")
        build.add_edge("librarian_agent", END)
        return build.compile()

    def run(self, claim_text: str) -> dict: # api entry pt
        initial_state = {
            "claim": claim_text,
            "verification_report": {},
            "final_action": "PENDING",
            "error": ""
        }
        final_output = self.graph.invoke(initial_state)

        try:
            cursor = self.sql_manager.conn.cursor()
            cursor.execute(
                """INSERT INTO verification_history (claim_text, agent_action, final_action)
                   VALUES (?, ?, ?)""",
                (
                    claim_text,
                    final_output.get("error") if final_output.get("error") else "Workflow executed successfully",
                    final_output.get("final_action", "FLAG")
                )
            )
            self.sql_manager.conn.commit()
            cursor.close()
            logger.info("Verification event successfully logged to history trail.")
        except Exception as hist_err:
            logger.error(f"Failed to record run history log: {hist_err}")
        return final_output  ## shouldve returned result i again called last time