import logging
from typing import TypedDict
import os
from Backend.agents.scout import ScoutAgent
from Backend.agents.librarian import LibrarianAgent
from langgraph.graph import StateGraph, END

logger = logging.getLogger(__name__)

class GraphState(TypedDict):
    claim: str
    verification_report: dict
    final_action: str
    error: str

class Workflow:
    def __init__(self, db_conn, chroma_collection):
        tavily_key = os.getenv("TAVILY_API_KEY", "")
        if not tavily_key:
            logger.warning("Tavily API key is missing from environment variables!")
        #
        self.scout = ScoutAgent(tavily_api_key=tavily_key)
        self.librarian = LibrarianAgent(db_conn=db_conn, chroma_collection=chroma_collection)
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
        try:
            decision = self.librarian.check(claim_text, report_data)
            return {"final_action": decision.get("action", "FLAG")}
        except Exception as e:
            logger.error(f"Librarian node crashed: {e}")
            return {"error": f"Librarian pipeline failed: {str(e)}", "final_action": "FLAG"}

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
        return self.graph.invoke(initial_state)