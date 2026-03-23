import os
from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv()

class Settings(BaseSettings):
    # Database
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./housing_metrics.db")

    # CMHC Data URLs
    cmhc_rental_market_url: str = "https://www.cmhc-schl.gc.ca/professionals/housing-markets-data-and-research/housing-data/data-tables/rental-market/rental-market-report-data-tables"
    cmhc_housing_starts_url: str = "https://www.cmhc-schl.gc.ca/professionals/housing-markets-data-and-research/housing-data/data-tables/housing-market-data/starts-completions-units-under-construction-geography"

    # Geographic identifiers
    kcw_cma_name: str = "Kitchener-Cambridge-Waterloo"
    kcw_cma_code: str = "541"  # CMHC CMA code

    # Scheduler settings
    enable_scheduler: bool = True

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()


# Data categories
class HousingCategory:
    VACANCY_RATE = "vacancy_rate"
    HOUSING_STARTS = "housing_starts"
    HOUSING_COMPLETIONS = "housing_completions"


# Data sources
class DataSource:
    CMHC = "cmhc"
