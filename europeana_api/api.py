"""
Europeana API Client
-------------------
Client for the Europeana API.
Provides methods to search for documents and retrieve metadata.
"""

import logging
import requests
import os
from datetime import datetime
from typing import Dict, Any, List, Optional, Union
from urllib.parse import quote

# Set up logging
logger = logging.getLogger(__name__)

class EuropeanaAPI:
    """
    Client for the Europeana API.
    Provides methods to search for documents and retrieve metadata.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the Europeana API client.
        
        Args:
            api_key: Europeana API key (optional, can also be set via EUROPEANA_API_KEY environment variable)
        """
        # Try to get API key from environment if not provided
        self.api_key = api_key or os.environ.get('EUROPEANA_API_KEY')
        if not self.api_key:
            logger.warning("No Europeana API key provided. Set EUROPEANA_API_KEY environment variable or pass api_key parameter.")
        
        # Set base URLs for different API endpoints
        self.search_url = "https://api.europeana.eu/record/v2/search.json"
        self.record_url = "https://api.europeana.eu/record/v2/record"
        
        logger.info("Europeana API client initialized")
    
    def _check_api_key(self) -> None:
        """
        Check if API key is available.
        
        Raises:
            ValueError: If no API key is available
        """
        if not self.api_key:
            raise ValueError("No Europeana API key available. Set EUROPEANA_API_KEY environment variable or pass api_key parameter.")
    
    def search(self, 
               query: str, 
               rows: int = 10,
               start: int = 1,
               profile: str = "standard",
               **kwargs) -> Dict[str, Any]:
        """
        Search for documents in the Europeana digital library.
        
        Args:
            query: Search query
            rows: Number of results to return (default: 10)
            start: Starting record for pagination (default: 1)
            profile: Result profile (minimal, standard, rich, portal)
            **kwargs: Additional query parameters
            
        Returns:
            Dictionary containing search results and metadata
        """
        self._check_api_key()
        
        # Prepare parameters
        params = {
            'wskey': self.api_key,
            'query': query,
            'rows': rows,
            'start': start,
            'profile': profile
        }
        
        # Add additional parameters from kwargs
        params.update(kwargs)
        
        try:
            # Make API request
            response = requests.get(self.search_url, params=params)
            response.raise_for_status()
            
            # Parse JSON response
            data = response.json()
            
            # Add metadata for easier processing
            results = {
                "metadata": {
                    "query": query,
                    "total_records": data.get("totalResults", 0),
                    "records_returned": len(data.get("items", [])),
                    "date_retrieved": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                },
                "records": data.get("items", []),
                "facets": data.get("facets", []),
                "raw_response": data
            }
            
            return results
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Error during Europeana API request: {e}")
            return {
                "error": str(e),
                "query": query,
                "parameters": params
            }
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return {
                "error": str(e),
                "query": query
            }
    
    def get_record(self, record_id: str) -> Dict[str, Any]:
        """
        Get detailed information about a specific record.
        
        Args:
            record_id: Europeana record ID
            
        Returns:
            Dictionary containing record data
        """
        self._check_api_key()
        
        # Ensure record ID is in the correct format
        record_id = record_id.strip('/')
        
        # URL encode the record ID with UTF-8 encoding
        encoded_record_id = quote(record_id, safe='', encoding='utf-8')
        
        url = f"https://api.europeana.eu/record/v2/{encoded_record_id}.json"
        
        try:
            response = requests.get(
                url,
                params={"wskey": self.api_key},
                headers={"Accept": "application/json", "Accept-Charset": "utf-8"},
                timeout=10
            )
            response.raise_for_status()
            
            # Parse JSON response with UTF-8 encoding
            data = response.json()
            
            # Add metadata for processing
            result = {
                "metadata": {
                    "record_id": record_id,
                    "date_retrieved": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                },
                "record": data.get("object", {}),
                "raw_response": data
            }
            
            return result
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Error during Europeana API record request: {e}")
            return {
                "error": str(e),
                "record_id": record_id,
                "status_code": getattr(e.response, 'status_code', None)
            }
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return {
                "error": str(e),
                "record_id": record_id
            }
    
    def extract_thumbnail(self, record: Dict[str, Any]) -> Optional[str]:
        """
        Extract thumbnail URL from a record.
        
        Args:
            record: Record data
            
        Returns:
            Thumbnail URL or None if not found
        """
        # Check if this is a search result
        if "edmIsShownBy" in record:
            if isinstance(record["edmIsShownBy"], list) and record["edmIsShownBy"]:
                return record["edmIsShownBy"][0]
            return record.get("edmIsShownBy")
        
        # For full records
        if "aggregations" in record:
            for agg in record.get("aggregations", []):
                if "edmIsShownBy" in agg:
                    if isinstance(agg["edmIsShownBy"], list) and agg["edmIsShownBy"]:
                        return agg["edmIsShownBy"][0]
                    return agg.get("edmIsShownBy")
        
        return None
    
    def extract_image_url(self, record: Dict[str, Any]) -> Optional[str]:
        """
        Extract the best quality image URL from a record.
        
        Args:
            record: Record data
            
        Returns:
            Image URL or None if not found
        """
        # Check if this is a search result
        if "edmObject" in record:
            if isinstance(record["edmObject"], list) and record["edmObject"]:
                return record["edmObject"][0]
            return record.get("edmObject")
        
        # For full records
        if "aggregations" in record:
            for agg in record.get("aggregations", []):
                if "edmObject" in agg:
                    if isinstance(agg["edmObject"], list) and agg["edmObject"]:
                        return agg["edmObject"][0]
                    return agg.get("edmObject")
        
        return None