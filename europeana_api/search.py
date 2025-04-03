"""
Search utilities for the Europeana API.
Provides functions to build different types of search queries.
"""

from typing import Dict, Any, List, Optional, Union
from .api import EuropeanaAPI
from .config import DEFAULT_MAX_RESULTS, DEFAULT_START_RECORD, DEFAULT_PROFILE


class SearchAPI:
    """
    Search utilities for the Europeana API.
    """
    
    def __init__(self, europeana_api: EuropeanaAPI):
        """
        Initialize the Search API.
        
        Args:
            europeana_api: An initialized EuropeanaAPI instance
        """
        self.europeana_api = europeana_api
    
    def search(self, 
               query: str, 
               rows: int = DEFAULT_MAX_RESULTS,
               start: int = DEFAULT_START_RECORD,
               profile: str = DEFAULT_PROFILE,
               **kwargs) -> Dict[str, Any]:
        """
        Basic search functionality.
        
        Args:
            query: Search query
            rows: Number of results (default: 10)
            start: Starting record (default: 1)
            profile: Result profile (default: standard)
            **kwargs: Additional query parameters
            
        Returns:
            Dictionary containing search results
        """
        return self.europeana_api.search(query, rows, start, profile, **kwargs)
    
    def search_by_title(
        self,
        title: str,
        exact_match: bool = False,
        rows: int = DEFAULT_MAX_RESULTS,
        start: int = DEFAULT_START_RECORD,
        profile: str = DEFAULT_PROFILE
    ) -> Dict[str, Any]:
        """
        Search for documents in the Europeana digital library by title.
        
        Args:
            title: The title to search for
            exact_match: If True, search for the exact title; otherwise, search for title containing the words
            rows: Number of results (default: 10)
            start: Starting record (default: 1)
            profile: Result profile (default: standard)
            
        Returns:
            Dictionary containing search results and metadata
        """
        query = f'title:"{title}"' if exact_match else f'title:{title}'
        
        return self.europeana_api.search(query, rows, start, profile)
    
    def search_by_creator(
        self,
        creator: str,
        exact_match: bool = False,
        rows: int = DEFAULT_MAX_RESULTS,
        start: int = DEFAULT_START_RECORD,
        profile: str = DEFAULT_PROFILE
    ) -> Dict[str, Any]:
        """
        Search for documents in the Europeana digital library by creator.
        
        Args:
            creator: The creator/author name to search for
            exact_match: If True, search for the exact name; otherwise, search for name containing the words
            rows: Number of results (default: 10)
            start: Starting record (default: 1)
            profile: Result profile (default: standard)
            
        Returns:
            Dictionary containing search results and metadata
        """
        query = f'creator:"{creator}"' if exact_match else f'creator:{creator}'
        
        return self.europeana_api.search(query, rows, start, profile)
    
    def search_by_year(
        self,
        year: Union[str, int],
        rows: int = DEFAULT_MAX_RESULTS,
        start: int = DEFAULT_START_RECORD,
        profile: str = DEFAULT_PROFILE
    ) -> Dict[str, Any]:
        """
        Search for documents in the Europeana digital library by year.
        
        Args:
            year: The year to search for (YYYY)
            rows: Number of results (default: 10)
            start: Starting record (default: 1)
            profile: Result profile (default: standard)
            
        Returns:
            Dictionary containing search results and metadata
        """
        query = f'YEAR:{year}'
        
        return self.europeana_api.search(query, rows, start, profile)
    
    def search_by_type(
        self,
        doc_type: str,
        rows: int = DEFAULT_MAX_RESULTS,
        start: int = DEFAULT_START_RECORD,
        profile: str = DEFAULT_PROFILE
    ) -> Dict[str, Any]:
        """
        Search for documents in the Europeana digital library by document type.
        
        Args:
            doc_type: The document type to search for (e.g., IMAGE, TEXT, VIDEO, SOUND, 3D)
            rows: Number of results (default: 10)
            start: Starting record (default: 1)
            profile: Result profile (default: standard)
            
        Returns:
            Dictionary containing search results and metadata
        """
        query = '*:*'  # Search for everything
        
        # Add filter for document type
        return self.europeana_api.search(query, rows, start, profile, qf=f'TYPE:{doc_type.upper()}')
    
    def search_by_provider(
        self,
        provider: str,
        rows: int = DEFAULT_MAX_RESULTS,
        start: int = DEFAULT_START_RECORD,
        profile: str = DEFAULT_PROFILE
    ) -> Dict[str, Any]:
        """
        Search for documents in the Europeana digital library by content provider.
        
        Args:
            provider: The provider name to search for
            rows: Number of results (default: 10)
            start: Starting record (default: 1)
            profile: Result profile (default: standard)
            
        Returns:
            Dictionary containing search results and metadata
        """
        query = '*:*'  # Search for everything
        
        # Add filter for provider
        return self.europeana_api.search(query, rows, start, profile, qf=f'PROVIDER:"{provider}"')
    
    def search_by_rights(
        self,
        rights: str,
        rows: int = DEFAULT_MAX_RESULTS,
        start: int = DEFAULT_START_RECORD,
        profile: str = DEFAULT_PROFILE
    ) -> Dict[str, Any]:
        """
        Search for documents in the Europeana digital library by rights statement.
        
        Args:
            rights: The rights statement to search for (e.g., "http://creativecommons.org/publicdomain/mark/1.0/")
            rows: Number of results (default: 10)
            start: Starting record (default: 1)
            profile: Result profile (default: standard)
            
        Returns:
            Dictionary containing search results and metadata
        """
        query = '*:*'  # Search for everything
        
        # Add filter for rights
        return self.europeana_api.search(query, rows, start, profile, qf=f'RIGHTS:"{rights}"')
    
    def advanced_search(
        self,
        query: str,
        filters: List[str] = None,
        rows: int = DEFAULT_MAX_RESULTS,
        start: int = DEFAULT_START_RECORD,
        profile: str = DEFAULT_PROFILE,
        facets: List[str] = None,
        sort: str = None
    ) -> Dict[str, Any]:
        """
        Perform an advanced search with multiple filters and options.
        
        Args:
            query: Main search query
            filters: List of query filters (qf parameters) to apply
            rows: Number of results (default: 10)
            start: Starting record (default: 1)
            profile: Result profile (default: standard)
            facets: List of facets to request
            sort: Sort order (e.g., 'score+desc', 'timestamp_created+asc')
            
        Returns:
            Dictionary containing search results and metadata
        """
        # Prepare params
        params = {}
        
        # Add filters if provided
        if filters:
            params['qf'] = filters
        
        # Add facets if provided
        if facets:
            params['facet'] = facets
        
        # Add sort if provided
        if sort:
            params['sort'] = sort
        
        return self.europeana_api.search(query, rows, start, profile, **params)