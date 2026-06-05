from typing import TypedDict
from pydantic import BaseModel, Field
import requests
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate

class VerificationReport(TypedDict):
    verdict: str
    evidence: list[str]
    confidence: float

class ScoutSchema(BaseModel):
    verdict: str = Field(description="Must be exactly 'REAL', 'FAKE', or 'UNCERTAIN'")
    confidence: float = Field(description="Confidence score from 0.0 to 1.0 based on evidence quality")
    reasoning: str = Field(description="A brief explanation summarizing why this verdict was chosen")

class ScoutAgent:
    def __init__(self, tavily_api_key: str):
        self.tavily_api_key = tavily_api_key
        self.search_url = "https://api.tavily.com/search"
        self.llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)

    def search(self, query: str) -> dict: # inputs the query text
        payload = {
            "api_key": self.tavily_api_key,
            "query": query,
            "search_depth": "basic",
            "max_results": 4
        }
        resp = requests.post(self.search_url, json=payload, timeout=30) # i choose 30 but we can shorten though 30 was fine
        resp.raise_for_status()
        return resp.json()

    def investigate(self, claim: str) -> VerificationReport:
        search_data = self.search(claim)
        source = [r.get("url", "") for r in search_data.get("results", []) if r.get("url")]
        context = "\n".join([f"Source Content : {r.get( 'content')}" for r in search_data.get("results", [])])
        prompt = ChatPromptTemplate.from_messages([
            ("system", (
                "You are an expert fact-checking agent. Analyze the provided web search context "
                "to determine if the user's claim is REAL, FAKE, or UNCERTAIN.\n\n"
                "Context:\n{context}"
            )),
            ("human", "Claim to verify: {claim}")
        ])
        structured_llm = self.llm.with_structured_output(ScoutSchema)
        chain = prompt | structured_llm
        analysis = chain.invoke({"context": context, "claim": claim})
        return {
            "verdict": analysis.verdict.upper(),
            "evidence": source,
            "confidence": analysis.confidence
        }