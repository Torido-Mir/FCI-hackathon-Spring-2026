import logging
from typing import Optional
import requests
import pandas as pd

logger = logging.getLogger(__name__)


class BaseFetcher:
    """Base class for data collectors with retry logic"""

    def __init__(self, name: str, max_retries: int = 3):
        self.name = name
        self.max_retries = max_retries

    def fetch(self) -> pd.DataFrame:
        """
        Fetch data from the source and return as DataFrame.
        Must be implemented by subclasses.
        """
        raise NotImplementedError("Subclasses must implement fetch()")

    def _get_with_retry(self, url: str, headers: Optional[dict] = None, **kwargs) -> requests.Response:
        """
        Make HTTP GET request with retry logic.

        Args:
            url: URL to fetch
            headers: Optional headers dict
            **kwargs: Additional arguments to pass to requests.get()

        Returns:
            Response object

        Raises:
            requests.RequestException: If all retries fail
        """
        for attempt in range(1, self.max_retries + 1):
            try:
                response = requests.get(url, headers=headers, timeout=30, **kwargs)
                response.raise_for_status()
                logger.info(f"{self.name}: Successfully fetched {url}")
                return response
            except requests.RequestException as e:
                logger.warning(f"{self.name}: Attempt {attempt}/{self.max_retries} failed: {e}")
                if attempt == self.max_retries:
                    logger.error(f"{self.name}: All retries exhausted for {url}")
                    raise
                continue

        raise RuntimeError(f"Failed to fetch {url} after {self.max_retries} attempts")
