from langfuse import Langfuse
import os
from src.core.config import LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_HOST
from src.utils.logging_config import get_logger

logger = get_logger("langfuse_client")

class LangfuseManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(LangfuseManager, cls).__new__(cls)
            cls._instance._client = None
        return cls._instance

    @property
    def client(self) -> Langfuse:
        if self._client is None:
            if LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY:
                try:
                    self._client = Langfuse(
                        public_key=LANGFUSE_PUBLIC_KEY,
                        secret_key=LANGFUSE_SECRET_KEY,
                        host=LANGFUSE_HOST
                    )
                    logger.info(f"Langfuse Client initialized (Host: {LANGFUSE_HOST})")
                except Exception as e:
                    logger.error(f"Failed to initialize Langfuse Client: {e}")
            else:
                logger.warning("Langfuse credentials missing. Tracing might be limited.")
        return self._client

    def score_trace(self, trace_id: str, name: str, value: float, comment: str = None):
        """Sends a numerical score to a specific trace."""
        if not self.client: return
        try:
            self.client.score(
                trace_id=trace_id,
                name=name,
                value=value,
                comment=comment
            )
            logger.info(f"Langfuse Trace {trace_id} scored: {name}={value}")
        except Exception as e:
            logger.warning(f"Failed to score trace {trace_id}: {e}")

    def add_to_dataset(self, dataset_name: str, input_data: any, output_data: any, metadata: dict = None, session_id: str = None):
        """Adds an example to a Langfuse dataset for training."""
        if not self.client: return
        try:
            self.client.create_dataset_item(
                dataset_name=dataset_name,
                input=input_data,
                expected_output=output_data,
                metadata=metadata
            )
            logger.info(f"Added item to Langfuse Dataset '{dataset_name}'")
        except Exception as e:
            logger.warning(f"Failed to add item to dataset '{dataset_name}': {e}")

    def get_session_traces(self, session_id: str):
        """Fetch all traces for a session for training analysis."""
        if not self.client: return []
        try:
            # Langfuse SDK pagination or direct fetch
            return self.client.get_traces(session_id=session_id)
        except Exception as e:
            logger.warning(f"Failed to fetch session traces: {e}")
            return []

# Singleton Instance
langfuse_manager = LangfuseManager()

def get_langfuse():
    """Returns the singleton Langfuse client."""
    return langfuse_manager.client
