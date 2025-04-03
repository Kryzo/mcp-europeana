"""
Configuration constants for the Europeana API.
"""

# Default API parameters
DEFAULT_MAX_RESULTS = 10
DEFAULT_START_RECORD = 1
DEFAULT_PROFILE = "standard"  # Options: minimal, standard, rich, portal

# API URLs
EUROPEANA_SEARCH_API_URL = "https://api.europeana.eu/record/v2/search.json"
EUROPEANA_RECORD_API_URL = "https://api.europeana.eu/record/v2"

# Document Types in Europeana
DOCUMENT_TYPES = {
    "IMAGE": "Images",
    "TEXT": "Texts",
    "VIDEO": "Videos",
    "SOUND": "Audio",
    "3D": "3D Objects"
}

# Common rights statements
RIGHTS_STATEMENTS = {
    "public": "http://creativecommons.org/publicdomain/mark/1.0/",
    "cc0": "http://creativecommons.org/publicdomain/zero/1.0/",
    "cc-by": "http://creativecommons.org/licenses/by/",
    "cc-by-sa": "http://creativecommons.org/licenses/by-sa/",
    "cc-by-nc": "http://creativecommons.org/licenses/by-nc/",
    "cc-by-nc-sa": "http://creativecommons.org/licenses/by-nc-sa/",
    "cc-by-nc-nd": "http://creativecommons.org/licenses/by-nc-nd/",
    "cc-by-nd": "http://creativecommons.org/licenses/by-nd/"
}

# Facet fields available in Europeana
FACET_FIELDS = [
    "TYPE",
    "LANGUAGE",
    "YEAR",
    "COUNTRY",
    "CONTRIBUTOR",
    "DATA_PROVIDER",
    "PROVIDER",
    "RIGHTS",
    "UGC",
    "TEXT_FULLTEXT"
]