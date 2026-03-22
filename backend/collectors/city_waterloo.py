import logging
import pandas as pd
from collectors.base import BaseFetcher

logger = logging.getLogger(__name__)


class CityWaterlooFetcher(BaseFetcher):
    """Fetch data from City of Waterloo open data / ArcGIS API"""

    BASE_URL = "https://gis.waterloo.ca/arcgis/rest/services/"

    def __init__(self):
        super().__init__("CityWaterloo")

    def fetch(self) -> pd.DataFrame:
        """
        Fetch local employment and sector data from City of Waterloo.

        Returns:
            DataFrame with columns: metric_name, value, unit, source_url
        """
        # TODO: implement City of Waterloo ArcGIS REST API call
        # or CSV download from open data portal
        # See: https://www.waterloo.ca/en/government/open-data

        logger.info("Fetching data from City of Waterloo")

        # Placeholder DataFrame
        data = {
            "metric_name": ["Employment by sector - Technology", "Business licenses issued"],
            "value": [15000, 1250],
            "unit": ["count", "count"],
            "source_url": [
                "https://www.waterloo.ca/en/government/open-data",
                "https://www.waterloo.ca/en/government/open-data"
            ]
        }

        df = pd.DataFrame(data)
        logger.info(f"CityWaterloo: Fetched {len(df)} metrics")
        return df
