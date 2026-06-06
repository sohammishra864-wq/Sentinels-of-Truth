import sqlite3
import json
from typing import List, Dict, Optional, Any
import logging
logger = logging.getLogger(__name__)
class SQLite_manager:
    def __init__(self , conn: sqlite3.Connection):
        self.conn = conn
        self.conn.row_factory = sqlite3.Row # each becomes dictionary new thing learned
        self.cursor = self.conn.cursor()

    def insert_claim(self,text: str, verdict: str, confidence: float, sources: List[str]) -> int:
        try: # this came as error so fixing now
            if sources is None:
                sanitized_sources = []
            elif isinstance(sources, str):
                sanitized_sources = [sources]
            elif isinstance(sources, list):
                sanitized_sources = [str(s) for s in sources]
            else:
                sanitized_sources = list(sources)
            self.cursor.execute("""INSERT INTO claims(claim_text , verdict , confidence,sources) VALUES (?,?,?,?)""", (text, verdict, confidence, json.dumps(sanitized_sources)  ))
            # json.dumps in documentation gives as json format in sql its not there
            self.conn.commit()
            return self.cursor.lastrowid # primary key
        except sqlite3.IntegrityError: # if unique not satisfied i mean need to change it later learrnign about any other method
            raise ValueError("This claim already exists")
    def check_existing_claim(self, text: str) -> Optional[Dict[str, Any]]:
        self.cursor.execute(""" SELECT * FROM claims WHERE claim_text = ? """, (text,))
        # self.conn.commit() dont commit here directly as there might raise some issue
        row = self.cursor.fetchone() # keep cursor in execute than con i had an error that why misunderstood it
        return dict(row) if row else None
    def insert_conflict(self, text : str , existing_id : int ) -> int:
        try:
            self.cursor.execute("""INSERT INTO conflicts(new_claim_text, existing_claim_id , status, created_at,updated_at) values (?,?,'PENDING',datetime('now'),datetime('now'))""", (text, existing_id))
            self.conn.commit()
            return self.cursor.lastrowid
        except Exception as e:
            logger.error(f"Failed to insert into conflicts table: {e}")
            raise e

    def close(self) -> None:
        self.conn.close()

