"""
Europeana API Package
-------------------
This package provides tools to search and retrieve information from the Europeana digital library,
Europe's platform for cultural heritage.
"""

from .api import EuropeanaAPI
from .search import SearchAPI
from .record import RecordAPI
from .sequential_reporting import (
    SequentialReportingServer, 
    EUROPEANA_SEQUENTIAL_REPORTING_TOOL,
)
from .config import (
    DEFAULT_MAX_RESULTS, 
    DEFAULT_START_RECORD,
    DEFAULT_PROFILE,
    EUROPEANA_SEARCH_API_URL,
    EUROPEANA_RECORD_API_URL,
    DOCUMENT_TYPES,
    RIGHTS_STATEMENTS,
    FACET_FIELDS
)
import logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("europeana_api.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)
__all__ = [
    'EuropeanaAPI',
    'SearchAPI',
    'RecordAPI',
    'SequentialReportingServer',
    'EUROPEANA_SEQUENTIAL_REPORTING_TOOL',
    'DEFAULT_MAX_RESULTS',
    'DEFAULT_START_RECORD',
    'DEFAULT_PROFILE',
    'EUROPEANA_SEARCH_API_URL',
    'EUROPEANA_RECORD_API_URL',
    'DOCUMENT_TYPES',
    'RIGHTS_STATEMENTS',
    'FACET_FIELDS'
]