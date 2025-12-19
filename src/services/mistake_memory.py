import json
import os
from threading import Lock
from src.utils.logging_config import get_logger

logger = get_logger("memory")

class MistakeMemory:
    def __init__(self, file_path="mistakes.json"):
        self.file_path = file_path
        self.lock = Lock()
        self.rules = self._load_rules()

    def _load_rules(self):
        if not os.path.exists(self.file_path):
            return []
        try:
            with open(self.file_path, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load mistakes.json: {e}")
            return []

    def _save_rules(self):
        try:
            with open(self.file_path, "w") as f:
                json.dump(self.rules, f, indent=4)
        except Exception as e:
            logger.error(f"Failed to save mistakes.json: {e}")

    def add_rule(self, rule_text):
        with self.lock:
            if rule_text not in self.rules:
                self.rules.append(rule_text)
                self._save_rules()
                logger.info(f"Learned New Rule: {rule_text}")

    def get_rules(self):
        # Return latest rules
        return self.rules

# Singleton Instance
MEMORY = MistakeMemory()
