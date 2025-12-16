import json
import os
import logging
from typing import List

logger = logging.getLogger(__name__)

MISTAKE_DB_PATH = "data/mistakes.json"

class MistakeMemory:
    def __init__(self):
        self.db_path = MISTAKE_DB_PATH
        self._ensure_db()
        
    def _ensure_db(self):
        if not os.path.exists(os.path.dirname(self.db_path)):
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        if not os.path.exists(self.db_path):
            with open(self.db_path, "w") as f:
                json.dump({"rules": []}, f)
                
    def get_rules(self) -> List[str]:
        try:
            with open(self.db_path, "r") as f:
                data = json.load(f)
            return data.get("rules", [])
        except Exception as e:
            logger.error(f"Failed to load mistakes: {e}")
            return []
            
    def add_rule(self, rule: str):
        try:
            with open(self.db_path, "r") as f:
                data = json.load(f)
            
            if rule not in data["rules"]:
                data["rules"].append(rule)
                
                with open(self.db_path, "w") as f:
                    json.dump(data, f, indent=2)
                logger.info(f"Learned new mistake rule: {rule}")
        except Exception as e:
            logger.error(f"Failed to add rule: {e}")

# Global Instance
MEMORY = MistakeMemory()
