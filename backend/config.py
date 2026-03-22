import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql://postgres:postgres@localhost:5432/millionready"

    # StatsCan API
    statscan_base_url: str = "https://www150.statcan.gc.ca/t1/wds/rest"
    statscan_building_permits_table: int = 34100292  # Table 34-10-0292-01
    statscan_kcw_cma_coordinate: str = "1.38"  # Kitchener-Cambridge-Waterloo CMA

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
    DWELLINGS_BUILT = "dwellings_built"
    VACANCY_RATE = "vacancy_rate"
    HOUSING_STARTS = "housing_starts"
    HOUSING_COMPLETIONS = "housing_completions"


# Data sources
class DataSource:
    STATSCAN = "statscan"
    CMHC = "cmhc"
