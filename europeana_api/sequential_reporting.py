"""
Europeana Sequential Reporting Tool
----------------------------------
This module provides a tool for generating structured reports based on research
from the Europeana digital library. It uses a sequential approach to gather sources,
analyze them, and generate a comprehensive report with proper citations.
"""

import json
import sys
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
import textwrap
from collections import Counter
import re
import traceback
from .api import EuropeanaAPI
from .search import SearchAPI
from .record import RecordAPI
import time

# Set up logging
logger = logging.getLogger(__name__)

# Constants
DEFAULT_PAGE_COUNT = 4
DEFAULT_SOURCE_COUNT = 10


@dataclass
class ReportSection:
    """
    Represents a section of the sequential report.
    """
    section_number: int
    total_sections: int
    content: str
    title: str
    is_bibliography: bool = False
    sources_used: List[int] = None
    next_section_needed: bool = True


class SequentialReportingServer:
    """
    Server for generating sequential reports based on Europeana research.
    """
    
    def __init__(self, europeana_api: EuropeanaAPI, search_api: SearchAPI, record_api: RecordAPI):
        """
        Initialize the Sequential Reporting Server.
        
        Args:
            europeana_api: An initialized EuropeanaAPI instance
            search_api: An initialized SearchAPI instance
            record_api: An initialized RecordAPI instance
        """
        self.europeana_api = europeana_api
        self.search_api = search_api
        self.record_api = record_api
        self.topic = None
        self.page_count = DEFAULT_PAGE_COUNT
        self.source_count = DEFAULT_SOURCE_COUNT
        self.sources = []
        self.report_sections = []
        self.plan = None
        self._current_step = 0
        self.include_graphics = False
        self.graphics = []
        self.provider_analysis = {}
        
    def validate_section_data(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate the input data for a section.
        
        Args:
            input_data: The input data for the section
            
        Returns:
            Validated input data
        """
        # First, ensure input_data is a dictionary
        if not isinstance(input_data, dict):
            raise ValueError(f"Expected dictionary input, got {type(input_data)}")
        
        validated_data = {}
        
        # Handle initialization with topic
        if 'topic' in input_data:
            validated_data['topic'] = str(input_data['topic'])
            if 'page_count' in input_data:
                try:
                    validated_data['page_count'] = int(input_data['page_count'])
                except (ValueError, TypeError):
                    validated_data['page_count'] = DEFAULT_PAGE_COUNT
            if 'source_count' in input_data:
                try:
                    validated_data['source_count'] = int(input_data['source_count'])
                except (ValueError, TypeError):
                    validated_data['source_count'] = DEFAULT_SOURCE_COUNT
            if 'include_graphics' in input_data:
                validated_data['include_graphics'] = bool(input_data['include_graphics'])
            return validated_data
            
        # Handle search_sources flag
        if 'search_sources' in input_data and input_data['search_sources']:
            validated_data['search_sources'] = True
            return validated_data
            
        # Handle confirm_sources flag - new step
        if 'confirm_sources' in input_data and input_data['confirm_sources']:
            validated_data['confirm_sources'] = True
            return validated_data
            
        # Handle confirmation step
        if 'confirm_sources' in input_data:
            validated_data['confirm_sources'] = bool(input_data['confirm_sources'])
            return validated_data
            
        # Handle confirmation step
        if 'confirm_sources' in input_data:
            validated_data['confirm_sources'] = bool(input_data['confirm_sources'])
            return validated_data
            
        # Handle confirm_sources flag
        if 'confirm_sources' in input_data and input_data['confirm_sources']:
            validated_data['confirm_sources'] = True
            return validated_data
        
        # Check if required fields are present for section data
        required_fields = ['section_number', 'total_sections']
        for field in required_fields:
            if field not in input_data:
                raise ValueError(f"Missing required field: {field}")
        
        # Get is_bibliography flag early as we need it for further validation
        is_bibliography = input_data.get('is_bibliography', False)
        
        # For non-bibliography sections, sources_used is required
        if not is_bibliography and (
            'sources_used' not in input_data or 
            not input_data['sources_used'] or 
            not isinstance(input_data['sources_used'], list)
        ):
            raise ValueError("Non-bibliography sections must include sources_used with at least one source ID")
        
        # Convert section_number and total_sections to integers if they're strings
        section_number = input_data['section_number']
        if isinstance(section_number, str) and section_number.isdigit():
            section_number = int(section_number)
        elif not isinstance(section_number, int):
            raise ValueError(f"Invalid sectionNumber: must be a number")
            
        total_sections = input_data['total_sections']
        if isinstance(total_sections, str) and total_sections.isdigit():
            total_sections = int(total_sections)
        elif not isinstance(total_sections, int):
            raise ValueError(f"Invalid totalSections: must be a number")
        
        # Get title
        title = input_data.get('title', f"Section {section_number}")
        
        # Get content (empty string if not provided)
        content = input_data.get('content', '')
        if content is None:
            content = ''
        if not isinstance(content, str):
            raise ValueError(f"Invalid content: must be a string")
        
        # Make sure content isn't empty for non-bibliography sections
        if not is_bibliography and len(content.strip()) < 10:  # Minimum content length
            raise ValueError("Content is required for non-bibliography sections and must be meaningful")
        
        # Get sources_used (empty list if not provided - but this should have been caught above for non-bibliography sections)
        sources_used = input_data.get('sources_used', [])
        if sources_used is None:
            sources_used = []
        
        # Get next_section_needed flag
        next_section_needed = input_data.get('next_section_needed', True)
        
        # Create and return ReportSection
        return {
            'section_number': section_number,
            'total_sections': total_sections,
            'title': title,
            'content': content,
            'is_bibliography': is_bibliography,
            'sources_used': sources_used,
            'next_section_needed': next_section_needed
        }
    
    def extract_and_analyze_pdf_content(self, record_id: str) -> Dict[str, Any]:
        """
        Extract text content from a PDF document and analyze it.
        
        Args:
            record_id: The Europeana record ID
            
        Returns:
            Dictionary with extracted text and analysis
        """
        try:
            # Extract PDF content using the new function
            pdf_result = self.record_api.extract_pdf_content(record_id=record_id, max_pages=10)
            
            if "error" in pdf_result:
                return {
                    "success": False,
                    "record_id": record_id,
                    "error": pdf_result.get("error", "Unknown error extracting PDF")
                }
            
            # Basic analysis of the content
            all_text = ""
            page_count = pdf_result.get("pages", 0)
            total_pages = pdf_result.get("total_pages", 0)
            
            # Concatenate all text for analysis
            for page in pdf_result.get("text", []):
                all_text += page.get("content", "") + "\n\n"
                
            # Check if we actually got usable text content
            if len(all_text.strip()) < 100:  # Minimum content threshold
                return {
                    "success": False,
                    "record_id": record_id,
                    "error": "Insufficient text content extracted from PDF (less than 100 characters)"
                }
            
            # Simple content analysis
            word_count = len(all_text.split())
            
            # Identify key terms (very basic approach)
            words = [w.lower() for w in all_text.split() if len(w) > 3]
            word_freq = Counter(words).most_common(10)
            key_terms = [term for term, count in word_freq if count > 1]
            
            # Extract metadata
            pdf_metadata = pdf_result.get("pdf_metadata", {})
            
            # Create analysis result
            analysis = {
                "success": True,
                "record_id": record_id,
                "source_url": pdf_result.get("source", ""),
                "page_count": page_count,
                "total_pages": total_pages,
                "analyzed_pages": min(page_count, 10),  # We limit to 10 pages for analysis
                "word_count": word_count,
                "key_terms": key_terms,
                "metadata": pdf_metadata,
                "text_sample": all_text[:1000] + "..." if len(all_text) > 1000 else all_text,
                "full_text": all_text,
                "content_summary": f"PDF document with {page_count} pages extracted out of {total_pages} total pages. Contains approximately {word_count} words."
            }
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error analyzing PDF content: {str(e)}")
            return {
                "success": False,
                "record_id": record_id,
                "error": f"Error analyzing PDF content: {str(e)}"
            }
    
    def search_sources(self, topic: str, source_count: int = DEFAULT_SOURCE_COUNT) -> List[Dict[str, Any]]:
        """
        Search for sources on the given topic using multiple strategies.
        
        Args:
            topic: The topic to search for
            source_count: The number of sources to retrieve
            
        Returns:
            List of sources as dictionaries
        """
        try:
            all_results = []
            seen_ids = set()
            search_metrics = {
                'total_attempts': 0,
                'successful_attempts': 0,
                'total_results': 0,
                'unique_results': 0,
                'retry_count': 0,
                'source_types': {
                    'IMAGE': 0,
                    'VIDEO': 0,
                    'SOUND': 0, 
                    'TEXT': 0,
                    'PDF': 0,
                    'OTHER': 0
                }
            }
            
            def process_result(result: Dict, result_type: str, index: int) -> Optional[Dict]:
                """Process a single search result and return a formatted source object."""
                try:
                    # Get unique identifier
                    id_field = result.get('id')
                    if not id_field:
                        return None
                        
                    # Skip duplicates
                    if id_field in seen_ids:
                        return None
                    seen_ids.add(id_field)
                    
                    # Get URLs
                    url = ''
                    if 'edmIsShownBy' in result:
                        url = result['edmIsShownBy'][0] if isinstance(result['edmIsShownBy'], list) else result['edmIsShownBy']
                    elif 'edmIsShownAt' in result:
                        url = result['edmIsShownAt'][0] if isinstance(result['edmIsShownAt'], list) else result['edmIsShownAt']
                    
                    # Skip if no URL found
                    if not url:
                        return None
                        
                    # Get title
                    title = result.get('title', ['Untitled'])[0] if isinstance(result.get('title', []), list) else result.get('title', 'Untitled')
                    
                    # Get description
                    description = result.get('description', [''])[0] if isinstance(result.get('description', []), list) else result.get('description', '')
                    if not description:
                        description = f"{result_type} related to {topic}: {title}"
                    
                    # Get provider
                    provider = result.get('provider', ['Unknown Provider'])[0] if isinstance(result.get('provider', []), list) else result.get('provider', 'Unknown Provider')
                    
                    # Get thumbnail
                    thumbnail = self.europeana_api.extract_thumbnail(result)
                    
                    # Get media type
                    media_type = result.get('type', 'Unknown')
                    search_metrics['source_types'][media_type if media_type in search_metrics['source_types'] else 'OTHER'] += 1
                    
                    # Get rights information
                    rights = result.get('rights', ['Unknown Rights'])[0] if isinstance(result.get('rights', []), list) else result.get('rights', 'Unknown Rights')
                    
                    # Get date
                    date = result.get('year', 'Unknown Date')
                    
                    # Check if URL looks like a PDF
                    is_pdf = url.lower().endswith('.pdf')
                    if is_pdf:
                        search_metrics['source_types']['PDF'] += 1
                    
                    return {
                        'id': index,
                        'title': title,
                        'description': description,
                        'url': url,
                        'provider': provider,
                        'thumbnail': thumbnail,
                        'media_type': media_type,
                        'rights': rights,
                        'date': date,
                        'europeanaId': id_field,
                        'is_pdf': is_pdf
                    }
                    
                except Exception as e:
                    logger.warning(f"Error processing {result_type} result: {str(e)}")
                    return None
            
            def search_with_retry(query: str, search_type: str = None, rows: int = source_count, max_retries: int = 3) -> List[Dict]:
                """Perform a search with retry logic."""
                search_metrics['total_attempts'] += 1
                for attempt in range(max_retries):
                    try:
                        # Check if the query has complex syntax like OR operators
                        has_complex_syntax = ' OR ' in query or ' AND ' in query
                        
                        # If we have a complex query, use the advanced_search directly
                        if has_complex_syntax:
                            filters = []
                            if search_type:
                                filters.append(f"TYPE:{search_type}")
                                
                            results = self.search_api.advanced_search(
                                query=query,
                                filters=filters,
                                rows=rows,
                                profile='standard'
                            )
                        else:
                            # Prepare search parameters
                            params = {
                                'query': query,
                                'rows': rows,
                                'profile': 'standard'
                            }
                            
                            # Add type filter if specified
                            if search_type:
                                params['type'] = search_type
                                
                            # Add language handling
                            if any(char in topic.lower() for char in 'àâçéèêëîïôûü'):  # French special characters
                                params['language'] = 'fr'
                                
                            # Perform search
                            results = self.europeana_api.search(**params)
                            
                        search_metrics['successful_attempts'] += 1
                        return results.get('records', [])
                    except Exception as e:
                        search_metrics['retry_count'] += 1
                        logger.warning(f"Search attempt {attempt + 1} failed: {str(e)}")
                        if attempt == max_retries - 1:
                            raise
                        time.sleep(2 ** attempt)  # Exponential backoff
                return []
            
            # Check if topic already contains OR operators
            has_or_operators = ' OR ' in topic
            
            # Strategy 1: Direct topic search (preserving OR operators if present)
            logger.info(f"Searching for topic: {topic}")
            try:
                results = search_with_retry(topic)
                for i, result in enumerate(results, 1):
                    source = process_result(result, 'Source', i)
                    if source:
                        all_results.append(source)
            except Exception as e:
                logger.warning(f"Initial search failed: {str(e)}")
            
            # If we need more sources and topic doesn't already have OR operators, try variations
            if len(all_results) < source_count and not has_or_operators:
                # Strategy 2: Try with quotes around the topic
                if len(all_results) < source_count:
                    # Don't quote if already contains quotes or OR operators
                    if not ('"' in topic or " OR " in topic):
                        quoted_topic = f'"{topic}"'
                        logger.info(f"Searching with quoted topic: {quoted_topic}")
                        try:
                            results = search_with_retry(quoted_topic)
                            for i, result in enumerate(results, len(all_results) + 1):
                                source = process_result(result, 'Source', i)
                                if source:
                                    all_results.append(source)
                        except Exception as e:
                            logger.warning(f"Quoted search failed: {str(e)}")
                
                # Strategy 3: Try with keywords connected by OR
                if len(all_results) < source_count:
                    # Split by spaces and also handle quoted phrases
                    import re
                    quoted_phrases = re.findall(r'"([^"]*)"', topic)
                    # Remove quoted phrases from the topic for word splitting
                    temp_topic = topic
                    for phrase in quoted_phrases:
                        temp_topic = temp_topic.replace(f'"{phrase}"', '')
                    
                    # Get individual words
                    words = [w for w in temp_topic.split() if len(w) > 3 and w.lower() not in ['and', 'or']]
                    
                    # Combine words and phrases
                    keywords = words + quoted_phrases
                    
                    if keywords:
                        keyword_query = " OR ".join([f'"{k}"' if ' ' in k else k for k in keywords])
                        logger.info(f"Searching with keywords: {keyword_query}")
                        try:
                            results = search_with_retry(keyword_query)
                            for i, result in enumerate(results, len(all_results) + 1):
                                source = process_result(result, 'Source', i)
                                if source:
                                    all_results.append(source)
                        except Exception as e:
                            logger.warning(f"Keyword search failed: {str(e)}")
                
                # Strategy 4: Try with type-specific searches
                if len(all_results) < source_count:
                    media_types = ['IMAGE', 'VIDEO', 'SOUND', 'TEXT']
                    for media_type in media_types:
                        if len(all_results) >= source_count:
                            break
                            
                        logger.info(f"Searching for {media_type.lower()} content")
                        try:
                            results = search_with_retry(topic, search_type=media_type, rows=source_count - len(all_results))
                            for i, result in enumerate(results, len(all_results) + 1):
                                source = process_result(result, media_type, i)
                                if source:
                                    all_results.append(source)
                        except Exception as e:
                            logger.warning(f"{media_type} search failed: {str(e)}")
            
            # Sort results by relevance and limit to source_count
            all_results.sort(key=lambda x: x.get('europeanaId', ''), reverse=True)
            final_results = all_results[:source_count] if source_count > 0 else all_results
            
            # Track providers for source diversity analysis
            self.provider_analysis = self._analyze_provider_diversity(final_results)
            
            # Log search metrics
            search_metrics['total_results'] = len(all_results)
            search_metrics['unique_results'] = len(seen_ids)
            logger.info(f"Search metrics: {search_metrics}")
            
            return final_results
            
        except Exception as e:
            logger.error(f"Error in multi-strategy search: {str(e)}")
            logger.error(traceback.format_exc())
            return []
    
    def search_graphics(self, topic: str, count: int = 5) -> List[Dict[str, Any]]:
        """
        Search for graphics (images, videos) related to the topic using multiple strategies.
        
        Args:
            topic: The topic to search for
            count: The number of graphics to retrieve
            
        Returns:
            List of graphics as dictionaries
        """
        try:
            all_graphics = []
            seen_ids = set()
            search_metrics = {
                'total_attempts': 0,
                'successful_attempts': 0,
                'total_results': 0,
                'unique_results': 0,
                'retry_count': 0
            }
            
            def process_result(result: Dict, result_type: str, index: int) -> Optional[Dict]:
                """Process a single search result and return a formatted graphic object."""
                try:
                    # Get unique identifier
                    id_field = result.get('id')
                    if not id_field:
                        return None
                        
                    # Skip duplicates
                    if id_field in seen_ids:
                        return None
                    seen_ids.add(id_field)
                    
                    # Get URLs
                    url = ''
                    if 'edmIsShownBy' in result:
                        url = result['edmIsShownBy'][0] if isinstance(result['edmIsShownBy'], list) else result['edmIsShownBy']
                    elif 'edmIsShownAt' in result:
                        url = result['edmIsShownAt'][0] if isinstance(result['edmIsShownAt'], list) else result['edmIsShownAt']
                    
                    # Skip if no URL found
                    if not url:
                        return None
                        
                    # Get title
                    title = result.get('title', ['Untitled'])[0] if isinstance(result.get('title', []), list) else result.get('title', 'Untitled')
                    
                    # Get description
                    description = result.get('description', [''])[0] if isinstance(result.get('description', []), list) else result.get('description', '')
                    if not description:
                        description = f"{result_type} related to {topic}: {title}"
                    
                    # Get provider
                    provider = result.get('provider', ['Unknown Provider'])[0] if isinstance(result.get('provider', []), list) else result.get('provider', 'Unknown Provider')
                    
                    # Get thumbnail
                    thumbnail = self.europeana_api.extract_thumbnail(result)
                    
                    # Get media type
                    media_type = result.get('type', 'Unknown')
                    
                    # Get rights information
                    rights = result.get('rights', ['Unknown Rights'])[0] if isinstance(result.get('rights', []), list) else result.get('rights', 'Unknown Rights')
                    
                    # Get date
                    date = result.get('year', 'Unknown Date')
                    
                    return {
                        'id': index,
                        'title': title,
                        'description': description,
                        'url': url,
                        'provider': provider,
                        'thumbnail': thumbnail,
                        'media_type': media_type,
                        'rights': rights,
                        'date': date,
                        'europeanaId': id_field
                    }
                    
                except Exception as e:
                    logger.warning(f"Error processing {result_type} result: {str(e)}")
                    return None
            
            def search_with_retry(query: str, search_type: str, rows: int, max_retries: int = 3) -> List[Dict]:
                """Perform a search with retry logic."""
                for attempt in range(max_retries):
                    try:
                        results = self.search_api.search_by_type(search_type, rows=rows, query=query)
                        search_metrics['successful_attempts'] += 1
                        return results.get('records', [])
                    except Exception as e:
                        search_metrics['retry_count'] += 1
                        logger.warning(f"Search attempt {attempt + 1} failed: {str(e)}")
                        if attempt == max_retries - 1:
                            raise
                        time.sleep(2 ** attempt)  # Exponential backoff
                return []
            
            # Strategy 1: Direct topic search for images
            logger.info(f"Searching for images related to: {topic}")
            try:
                image_results = search_with_retry(topic, 'IMAGE', count)
                for i, result in enumerate(image_results, 1):
                    graphic = process_result(result, 'Image', i)
                    if graphic:
                        all_graphics.append(graphic)
            except Exception as e:
                logger.warning(f"Image search failed: {str(e)}")
            
            # Strategy 2: Keyword-based image search
            if len(all_graphics) < count:
                keywords = [w for w in topic.split() if len(w) > 3]
                if keywords:
                    keyword_query = " OR ".join(keywords)
                    logger.info(f"Searching for images with keywords: {keyword_query}")
                    try:
                        keyword_results = search_with_retry(keyword_query, 'IMAGE', count - len(all_graphics))
                        for i, result in enumerate(keyword_results, len(all_graphics) + 1):
                            graphic = process_result(result, 'Image', i)
                            if graphic:
                                all_graphics.append(graphic)
                    except Exception as e:
                        logger.warning(f"Keyword image search failed: {str(e)}")
            
            # Strategy 3: Video search
            if len(all_graphics) < count:
                remaining = count - len(all_graphics)
                logger.info(f"Searching for videos related to: {topic}")
                try:
                    video_results = search_with_retry(topic, 'VIDEO', remaining)
                    for i, result in enumerate(video_results, len(all_graphics) + 1):
                        graphic = process_result(result, 'Video', i)
                        if graphic:
                            all_graphics.append(graphic)
                except Exception as e:
                    logger.warning(f"Video search failed: {str(e)}")
            
            # Strategy 4: Audio search
            if len(all_graphics) < count:
                remaining = count - len(all_graphics)
                logger.info(f"Searching for audio related to: {topic}")
                try:
                    audio_results = search_with_retry(topic, 'SOUND', remaining)
                    for i, result in enumerate(audio_results, len(all_graphics) + 1):
                        graphic = process_result(result, 'Audio', i)
                        if graphic:
                            all_graphics.append(graphic)
                except Exception as e:
                    logger.warning(f"Audio search failed: {str(e)}")
            
            # Sort results by relevance and limit to count
            all_graphics.sort(key=lambda x: x.get('europeanaId', ''), reverse=True)
            final_graphics = all_graphics[:count]
            
            # Log search metrics
            search_metrics['total_results'] = len(all_graphics)
            search_metrics['unique_results'] = len(seen_ids)
            logger.info(f"Graphics search metrics: {search_metrics}")
            
            return final_graphics
            
        except Exception as e:
            logger.error(f"Error in multi-strategy graphics search: {str(e)}")
            logger.error(traceback.format_exc())
            return []
    
    def process_section(self, input_data: Any) -> Dict[str, Any]:
        """
        Process a report section following a sequential approach.
        
        Args:
            input_data: The input data for the section
            
        Returns:
            Response data as a dictionary
        """
        try:
            # Validate the input data
            data = self.validate_section_data(input_data)
            
            # Initialize with topic
            if 'topic' in data:
                self.topic = data['topic']
                self.page_count = data.get('page_count', DEFAULT_PAGE_COUNT)
                self.source_count = data.get('source_count', DEFAULT_SOURCE_COUNT)
                self.include_graphics = data.get('include_graphics', False)
                self.sources = []
                self.graphics = []
                self.report_sections = []
                self._current_step = 0
                
                # Create a plan for the report
                self.plan = self.create_plan(self.topic, self.page_count)
                
                return {
                    'content': [{
                        'text': json.dumps({
                            'topic': self.topic,
                            'pageCount': self.page_count,
                            'sourceCount': self.source_count,
                            'includeGraphics': self.include_graphics,
                            'plan': self.plan,
                            'nextStep': 'Search for sources using the europeana_search tool'
                        })
                    }]
                }
            
            # Search for sources
            if data.get('search_sources', False):
                if not self.topic:
                    return {'content': [{'text': 'Error: No topic specified. Please initialize with a topic first.'}]}
                
                self.sources = self.search_sources(self.topic, self.source_count)
                
                # Prepare source summary
                media_counts = {
                    'IMAGE': 0,
                    'VIDEO': 0,
                    'SOUND': 0, 
                    'TEXT': 0,
                    'PDF': 0,
                    'OTHER': 0
                }
                
                # Get media type counts
                for source in self.sources:
                    media_type = source.get('media_type', 'OTHER')
                    media_counts[media_type if media_type in media_counts else 'OTHER'] += 1
                    if source.get('is_pdf', False):
                        media_counts['PDF'] += 1
                
                # Calculate total sources found
                total_found = len(self.sources)
                        
                # Check if we found any sources at all
                if total_found == 0:
                    return {
                        'content': [{
                            'text': json.dumps({
                                'error': "No sources found for the topic. Cannot proceed with report generation.",
                                'status': 'failed',
                                'message': "No sources could be found on this topic. Please try a different search query or topic."
                            })
                        }],
                        'isError': True
                    }
                
                # If graphics are requested, search for them
                if self.include_graphics:
                    self.graphics = self.search_graphics(self.topic, count=5)
                
                self._current_step = 1
                
                # Add source diversity information
                source_message = {}
                
                # Count PDFs with content
                pdf_sources = [source for source in self.sources if source.get('has_pdf', False) and source.get('pdf_content', {}).get('success', False)]
                
                # Prepare message about PDFs
                pdf_message = ""
                if pdf_sources:
                    pdf_message = f"Found {len(pdf_sources)} sources with PDF content. These have been automatically analyzed and the extracted text is available for your use. PDF content provides valuable primary source material."
                else:
                    pdf_message = "WARNING: No sources with readable PDF content were found. This may limit the ability to create a detailed factual report. DO NOT fabricate information - focus only on what is available in the metadata."
                
                # Generate source summary table
                source_summary = {
                    'totalFound': total_found,
                    'requestedSourceCount': self.source_count,
                    'sourcesReturned': len(self.sources),
                    'mediaTypeCounts': media_counts,
                    'sourcesWithPDFContent': len(pdf_sources),
                    'providersCount': self.provider_analysis.get('total_providers', 0),
                    'graphicsFound': len(self.graphics) if self.include_graphics else 0
                }
                
                is_confirmation_step = True  # Flag this as a confirmation step
                
                if self.provider_analysis.get('diverse_sources', False):
                    source_message = {
                        'confirmationRequired': True,  # Add this flag to signal confirmation is needed
                        'sourceSummary': source_summary,  # Add summary table
                        'sources': self.sources,
                        'graphics': self.graphics if self.include_graphics else [],
                        'sourceAnalysis': {
                            'message': f"Found {len(self.sources)} sources from {self.provider_analysis.get('total_providers', 0)} different providers. You should use sources from multiple providers in your report for diverse perspectives.",
                            'providerDistribution': self.provider_analysis.get('provider_distribution', {}),
                            'diverse': True
                        },
                        'pdfAnalysis': pdf_message,
                        'sourcesWithContent': len(pdf_sources) > 0,
                        'nextStep': 'Please confirm if you want to proceed with generating the report using these sources.'
                    }
                else:
                    source_message = {
                        'confirmationRequired': True,  # Add this flag to signal confirmation is needed
                        'sourceSummary': source_summary,  # Add summary table
                        'sources': self.sources,
                        'graphics': self.graphics if self.include_graphics else [],
                        'sourceAnalysis': {
                            'message': f"All sources are from a single provider: {self.provider_analysis.get('primary_provider', 'Unknown')}. Please note this limitation in your report.",
                            'providerDistribution': self.provider_analysis.get('provider_distribution', {}),
                            'diverse': False
                        },
                        'pdfAnalysis': pdf_message,
                        'sourcesWithContent': len(pdf_sources) > 0,
                        'nextStep': 'Please confirm if you want to proceed with generating the report using these sources.'
                    }
                
                return {
                    'content': [{
                        'text': json.dumps(source_message)
                    }]
                }
                
            # Process confirmation step
            if data.get('confirm_sources', False):
                # If user confirmed they want to proceed despite potentially limited sources
                self._current_step = 2  # Move to next step
                
                return {
                    'content': [{
                        'text': json.dumps({
                            'message': "Source selection confirmed. Proceeding with report generation.",
                            'nextStep': 'Create bibliography section'
                        })
                    }]
                }
            
            # Process section data for bibliography or content sections
            validated_input = self.validate_section_data(input_data)
            
            # Enforce citation requirements for non-bibliography sections
            if not validated_input.get('is_bibliography', False):
                # Require sources for non-bibliography sections
                if not validated_input.get('sources_used'):
                    return {
                        'content': [{
                            'text': json.dumps({
                                'error': "No sources cited. Every non-bibliography section must cite specific sources.",
                                'status': 'failed',
                                'message': "Please include sources_used parameter with IDs of sources used in this section."
                            })
                        }],
                        'isError': True
                    }
                
                # ENHANCED: Validate content has citations for each paragraph
                content = validated_input.get('content', '')
                sources_used = validated_input.get('sources_used', [])
                
                content_validation = self._verify_content_has_citations(content, sources_used)
                if not content_validation.get('valid', False):
                    return {
                        'content': [{
                            'text': json.dumps({
                                'error': "Content validation failed: " + content_validation.get('message', ''),
                                'status': 'failed',
                                'paragraph_issues': content_validation.get('paragraph_issues', []),
                                'message': "Ensure every substantial paragraph contains citations to source material."
                            })
                        }],
                        'isError': True
                    }
                
                # ENHANCED: Verify proper citations to each source in sources_used
                citation_check = self.verify_citations(content, sources_used)
                if not citation_check.get('valid', False):
                    return {
                        'content': [{
                            'text': json.dumps({
                                'error': "Citation validation failed: " + citation_check.get('message', ''),
                                'status': 'failed',
                                'uncited_sources': citation_check.get('uncited_sources', []),
                                'invalid_citations': citation_check.get('invalid_citations', []),
                                'uncited_paragraphs': citation_check.get('uncited_paragraphs', []),
                                'message': "Every source in sources_used must be cited in the content, and every paragraph must include at least one citation."
                            })
                        }],
                        'isError': True
                    }
                
                # ENHANCED: Analyze citation patterns for better enforcement
                citation_analysis = self.analyze_citation_patterns(content, sources_used)
                if not citation_analysis.get('valid', False):
                    # Not a hard failure but include a warning
                    warning_message = "Citation pattern warning: " + citation_analysis.get('message', '')
                else:
                    warning_message = None
            
            # Adjust total sections if needed
            if validated_input['section_number'] > validated_input['total_sections']:
                validated_input['total_sections'] = validated_input['section_number']
            
            # Add section to report
            self.report_sections.append(validated_input)
            
            # Format and display section
            formatted_section = self.format_section(validated_input)
            print(formatted_section, file=sys.stderr)
            
            # Update current step in plan
            if self.plan:
                self.plan["current_section"] = validated_input['section_number']
                if validated_input['section_number'] < len(self.plan["sections"]):
                    next_section_title = self.plan["sections"][validated_input['section_number']]["title"]
                    next_step = f"Create section {validated_input['section_number'] + 1}: {next_section_title}"
                else:
                    next_step = "Report complete"
            else:
                next_step = "Continue writing the report"
                if not validated_input['next_section_needed']:
                    next_step = "Report complete"
            
            # Calculate progress
            progress = (len(self.report_sections) / validated_input['total_sections']) * 100
            
            # Add source usage analysis if this is not a bibliography
            if not validated_input.get('is_bibliography', False) and validated_input.get('sources_used'):
                # Get the providers of the sources used in this section
                providers_used = []
                pdf_sources_used = []
                
                for source_id in validated_input.get('sources_used', []):
                    # Sources are 1-indexed, so adjust
                    if 0 <= source_id - 1 < len(self.sources):
                        source = self.sources[source_id - 1]
                        if 'provider' in source:
                            providers_used.append(source['provider'])
                        
                        # Check for PDF content
                        if source.get('has_pdf', False) and source.get('pdf_content', {}).get('success', False):
                            pdf_sources_used.append({
                                'id': source_id,
                                'title': source.get('title', 'Unknown Title'),
                                'pdf_content': source.get('pdf_content', {})
                            })
                
                # Analyze source diversity in this section
                provider_counts = Counter(providers_used)
                diverse_section = len(provider_counts) > 1
                
                # Check if any sources with actual content were used
                sources_with_content = len(pdf_sources_used) > 0
                if not sources_with_content:
                    warning_message = ("WARNING: None of the cited sources have extractable content. "
                                      "This severely limits the ability to make factual claims. "
                                      "DO NOT fabricate information - focus only on what is available in the metadata.")
                    # Add warning to section message
                else:
                    warning_message = None
                
                # Create source usage message
                if diverse_section:
                    source_analysis_message = f"This section uses sources from {len(provider_counts)} different providers. Continue using diverse sources in subsequent sections."
                else:
                    if providers_used:
                        source_analysis_message = f"This section uses sources from only one provider: {providers_used[0]}. Try to incorporate sources from other providers in the next sections if possible."
                    else:
                        source_analysis_message = "This section doesn't use any sources. Please include citations in your content."
                
                # Create PDF content message if applicable
                pdf_content_message = None
                if pdf_sources_used:
                    pdf_content_message = f"This section uses {len(pdf_sources_used)} sources with PDF content. Use the extracted text for direct quotes and primary source material."
                else:
                    pdf_content_message = "No sources with PDF content were used in this section. Be careful to limit claims to what is explicitly available in metadata."
            else:
                source_analysis_message = None
                pdf_content_message = None
                warning_message = None
            
            return {
                'content': [{
                    'text': json.dumps({
                        'sectionNumber': validated_input['section_number'],
                        'totalSections': validated_input['total_sections'],
                        'nextSectionNeeded': validated_input['next_section_needed'],
                        'progress': f"{progress:.1f}%",
                        'reportSectionsCount': len(self.report_sections),
                        'nextStep': next_step,
                        'sources': self.sources if validated_input['is_bibliography'] else None,
                        'sourceAnalysisMessage': source_analysis_message,
                        'pdfContentMessage': pdf_content_message,
                        'pdfSourcesUsed': pdf_sources_used if 'pdf_sources_used' in locals() and pdf_sources_used else None,
                        'sourceProviderCount': len(self.provider_analysis.get('provider_distribution', {})),
                        'imagesAvailable': len(self.graphics) > 0 if self.include_graphics else False,
                        'images': self.graphics[:3] if self.include_graphics and self.graphics else None,
                        'citationWarning': warning_message if 'warning_message' in locals() and warning_message else None,
                        'warningMessage': warning_message if 'warning_message' in locals() and warning_message else None,
                        'sourceDiversityReminder': "Remember to include proper references with links to original sources, and try to use sources from at least two different providers for varied perspectives.",
                        'noFabricationReminder': "CRITICAL: NEVER invent or fabricate any information. If sources are insufficient, explicitly state these limitations in your report.",
                        'citationReminder': "Every paragraph in your report must contain at least one citation to a source. All statements must be directly supported by the source material."
                    })
                }]
            }
        except ValueError as ve:
            return {
                'content': [{
                    'text': json.dumps({
                        'error': f"Validation error: {str(ve)}",
                        'status': 'failed',
                        'detailed_message': traceback.format_exc()
                    })
                }],
                'isError': True
            }
        except Exception as e:
            return {
                'content': [{
                    'text': json.dumps({
                        'error': f"Unexpected error: {str(e)}",
                        'status': 'failed',
                        'detailed_message': traceback.format_exc()
                    })
                }],
                'isError': True
            }
    

    def _verify_content_has_citations(self, content: str, sources_used: List[int]) -> Dict[str, Any]:
        """
        Verify that content contains appropriate citations for each paragraph 
        and uses sources from the sources_used list properly.
        
        Args:
            content: The section content to check
            sources_used: List of source IDs that should be cited
                
        Returns:
            Dictionary indicating if content passes verification and details about issues
        """
        if not sources_used:
            return {
                "valid": False,
                "message": "No sources provided in sources_used list."
            }
            
        # Split content into paragraphs for analysis
        paragraphs = [p for p in content.split('\n\n') if p.strip()]
        
        # Citation pattern including optional page numbers
        citation_regex = r"\[(\d+)(?:,\s*(?:p\.|page)\s*\d+)?\]"
        
        # Check each paragraph
        paragraph_issues = []
        for i, paragraph in enumerate(paragraphs):
            # Skip very short paragraphs (likely headers, separators, etc.)
            if len(paragraph.strip()) < 20:
                continue
                
            # Find all citations in this paragraph
            paragraph_citations = [int(match) for match in re.findall(citation_regex, paragraph)]
            
            # Check if paragraph has any citations
            if not paragraph_citations:
                paragraph_issues.append({
                    "index": i,
                    "text": paragraph[:100] + "..." if len(paragraph) > 100 else paragraph,
                    "issue": "Paragraph contains no citations"
                })
                continue
                
            # Check if paragraph cites sources that aren't in sources_used
            invalid_citations = [cite for cite in paragraph_citations if cite not in sources_used]
            if invalid_citations:
                paragraph_issues.append({
                    "index": i,
                    "text": paragraph[:100] + "..." if len(paragraph) > 100 else paragraph,
                    "issue": f"Paragraph contains invalid citations: {invalid_citations}"
                })
        
        # Result is valid if there are no paragraph issues
        valid = len(paragraph_issues) == 0
        
        return {
            "valid": valid,
            "paragraph_issues": paragraph_issues,
            "message": f"{len(paragraph_issues)} paragraphs with citation issues" if paragraph_issues else "All paragraphs properly cited"
        }
    
    def analyze_citation_patterns(self, content: str, sources_used: List[int]) -> Dict[str, Any]:
        """
        Analyze citation patterns in content to ensure proper source usage.
        This function provides more detailed analysis about how sources are used.
        
        Args:
            content: The section content to check
            sources_used: List of source IDs that should be cited
                
        Returns:
            Dictionary with detailed analysis results
        """
        results = {
            "valid": True,
            "source_usage": {},
            "citation_frequency": {},
            "paragraphs_without_citations": 0,
            "paragraphs_with_multiple_sources": 0,
            "all_paragraphs_cited": True,
            "all_sources_used": True,
            "message": ""
        }
        
        # Split content into paragraphs for analysis
        paragraphs = [p for p in content.split('\n\n') if p.strip()]
        
        # Citation pattern including optional page numbers
        citation_regex = r"\[(\d+)(?:,\s*(?:p\.|page)\s*\d+)?\]"
        
        # Initialize source usage count
        source_usage = {source_id: 0 for source_id in sources_used}
        paragraphs_with_citations = 0
        
        # Analyze each paragraph
        for paragraph in paragraphs:
            # Skip very short paragraphs
            if len(paragraph.strip()) < 20:
                continue
                
            # Find all citations in this paragraph
            paragraph_citations = [int(match) for match in re.findall(citation_regex, paragraph)]
            
            # Update the set of cited sources
            cited_sources = set(paragraph_citations)
            
            # Update source usage counts
            for source_id in cited_sources:
                if source_id in source_usage:
                    source_usage[source_id] += 1
                
            # Check if paragraph has any citations
            if paragraph_citations:
                paragraphs_with_citations += 1
                
                # Check if paragraph uses multiple sources
                if len(cited_sources) > 1:
                    results["paragraphs_with_multiple_sources"] += 1
            else:
                results["paragraphs_without_citations"] += 1
                results["all_paragraphs_cited"] = False
        
        # Update results
        results["source_usage"] = source_usage
        
        # Check if all sources are used
        unused_sources = [source_id for source_id, count in source_usage.items() if count == 0]
        if unused_sources:
            results["all_sources_used"] = False
        
        # Calculate citation frequency as percentage of paragraphs
        total_paragraphs = len(paragraphs)
        if total_paragraphs > 0:
            results["citation_frequency"] = paragraphs_with_citations / total_paragraphs * 100
        else:
            results["citation_frequency"] = 0
        
        # Set overall validity
        results["valid"] = results["all_paragraphs_cited"] and results["all_sources_used"]
        
        # Create message
        message_parts = []
        if not results["all_paragraphs_cited"]:
            message_parts.append(f"{results['paragraphs_without_citations']} paragraph(s) without citations")
        
        if not results["all_sources_used"]:
            unused = ", ".join(str(s) for s in unused_sources)
            message_parts.append(f"Unused sources: {unused}")
            
        if message_parts:
            results["message"] = ". ".join(message_parts)
        else:
            results["message"] = "All paragraphs properly cited and all sources used."
        
        return results

    def format_section(self, section: Dict[str, Any]) -> str:
        """
        Format a report section for display.
        
        Args:
            section: The report section to format
            
        Returns:
            Formatted section as a string
        """
        # Get section information
        section_number = section.get('section_number', 0)
        total_sections = section.get('total_sections', 0)
        title = section.get('title', 'Untitled')
        is_bibliography = section.get('is_bibliography', False)
        
        # Create a box for the section
        width = 80
        icon = "\033[93m📚\033[0m" if is_bibliography else "\033[94m📄\033[0m"  # Yellow for bibliography, blue for content
        
        header = f" {icon} Section {section_number}/{total_sections}: {title} "
        
        box = "┌" + "─" * (width - 2) + "┐\
"
        box += "│" + header + " " * (width - len(header) - 2) + "│\
"
        box += "├" + "─" * (width - 2) + "┤\
"
        
        # Add content
        content = section.get('content', '')
        if content:
            # Wrap content to fit in the box
            wrapped_content = textwrap.wrap(content, width=width-4)
            for line in wrapped_content:
                box += "│ " + line + " " * (width - len(line) - 4) + " │\
"
        
        # Add graphics if available and this is not a bibliography
        if not is_bibliography and self.include_graphics and self.graphics:
            # Find graphics relevant to this section
            section_graphics = []
            for graphic in self.graphics:
                # Simple relevance check - could be improved
                if any(term in graphic['title'].lower() for term in title.lower().split()):
                    section_graphics.append(graphic)
            
            # Add up to 2 graphics for this section
            if section_graphics:
                box += "│ " + " " * (width - 4) + " │\
"
                box += "│ " + "Graphics:" + " " * (width - 13) + " │\
"
                for graphic in section_graphics[:2]:
                    desc = f"- {graphic['description']}"
                    wrapped_desc = textwrap.wrap(desc, width=width-4)
                    for line in wrapped_desc:
                        box += "│ " + line + " " * (width - len(line) - 4) + " │\
"
                    box += "│ " + f"  URL: {graphic['url']}" + " " * (width - len(f"  URL: {graphic['url']}") - 4) + " │\
"
                    box += "│ " + f"  Provider: {graphic.get('provider', 'Unknown')}" + " " * (width - len(f"  Provider: {graphic.get('provider', 'Unknown')}") - 4) + " │\
"
        
        # Add source analysis if this is not a bibliography
        if not is_bibliography and section.get('sources_used'):
            box += "│ " + " " * (width - 4) + " │\
"
            box += "│ " + "Sources Used:" + " " * (width - 17) + " │\
"
            
            # List sources with providers
            sources_info = []
            pdf_sources_used = []
            
            for source_id in section.get('sources_used', []):
                # Sources are 1-indexed, so adjust
                if 0 <= source_id - 1 < len(self.sources):
                    source = self.sources[source_id - 1]
                    provider = source.get('provider', 'Unknown Provider')
                    source_type = source.get('type', 'Unknown')
                    has_pdf = source.get('has_pdf', False)
                    
                    # Add PDF indicator
                    pdf_indicator = " [PDF]" if has_pdf else ""
                    sources_info.append(f"[{source_id}] {source_type} from {provider}{pdf_indicator}")
                    
                    if has_pdf:
                        pdf_sources_used.append(source_id)
            
            # Check source diversity
            providers_used = []
            for source_id in section.get('sources_used', []):
                if 0 <= source_id - 1 < len(self.sources):
                    source = self.sources[source_id - 1]
                    if 'provider' in source:
                        providers_used.append(source['provider'])
            
            provider_counts = Counter(providers_used)
            diverse_section = len(provider_counts) > 1
            
            # Add source list
            for info in sources_info:
                box += "│ " + f"  {info}" + " " * (width - len(f"  {info}") - 4) + " │\
"
            
            # Add PDF content notification if any PDF sources were used
            if pdf_sources_used:
                box += "│ " + " " * (width - 4) + " │\
"
                pdf_message = f"This section uses {len(pdf_sources_used)} sources with PDF content. Use the extracted text for direct quotes and primary source material."
                box += "│ " + pdf_message + " " * (width - len(pdf_message) - 4) + " │\
"
            
            # Add diversity analysis
            if diverse_section:
                message = f"This section uses sources from {len(provider_counts)} different providers."
                box += "│ " + " " * (width - 4) + " │\
"
                box += "│ " + message + " " * (width - len(message) - 4) + " │\
"
            elif providers_used:
                message = f"This section uses sources from only one provider: {providers_used[0]}."
                box += "│ " + " " * (width - 4) + " │\
"
                box += "│ " + message + " " * (width - len(message) - 4) + " │\
"
                
        
        box += "└" + "─" * (width - 2) + "┘"
        
        return box

    def create_plan(self, topic: str, page_count: int = DEFAULT_PAGE_COUNT) -> Dict[str, Any]:
        """
        Create a sequential plan for the report based on the topic.
        
        Args:
            topic: The research topic
            page_count: Number of pages to generate
            
        Returns:
            A plan dictionary with sections and steps
        """
        # Calculate number of sections based on page count (1 page ≈ 2 sections + bibliography)
        total_sections = min(page_count * 2 + 1, 20)  # Cap at 20 sections
        
        # Create standard sections
        sections = [{"title": "Bibliography", "is_bibliography": True}]
        
        # Add introduction
        sections.append({"title": "Introduction", "is_bibliography": False})
        
        # Add content sections based on page count
        if page_count >= 2:
            sections.append({"title": "Historical Context", "is_bibliography": False})
        
        if page_count >= 3:
            sections.append({"title": "Main Analysis", "is_bibliography": False})
            sections.append({"title": "Key Findings", "is_bibliography": False})
        
        if page_count >= 4:
            sections.append({"title": "Detailed Examination", "is_bibliography": False})
            sections.append({"title": "Cultural Significance", "is_bibliography": False})
        
        # Add more sections for longer reports
        remaining_sections = total_sections - len(sections)
        for i in range(remaining_sections):
            sections.append({"title": f"Additional Analysis {i+1}", "is_bibliography": False})
        
        # Always end with conclusion
        sections.append({"title": "Conclusion", "is_bibliography": False})
        
        # Add PDF-specific steps if needed
        enhanced_steps = [
            "Initialize with topic",
            "Search for sources and extract PDF content",
            "Analyze PDF content for primary source material",
            "Create bibliography with PDFs marked",
            "Write introduction incorporating PDF insights",
            "Develop content sections using PDF extracts",
            "Include images when relevant to illustrate key points",
            "Write conclusion"
        ]
        
        return {
            "topic": topic,
            "total_sections": len(sections),
            "sections": sections,
            "current_section": 0,
            "steps": enhanced_steps,
            "current_step": 0,
            "next_step": "Search for sources and extract PDF content",
            "reportGuidelines": [
                "CRITICAL: NEVER invent or fabricate any information. If sources are insufficient, explicitly state this limitation.",
                "Every statement in the report MUST be directly supported by the content from the sources found.",
                "Use specific citations ([source_id], page X) for EVERY factual claim in the report.",
                "Always include proper references with links to the original sources.",
                "Use PDF content to extract direct quotes and primary source material.",
                "Include images when they help illustrate important concepts.",
                "Explicitly mention where you found each piece of information and explain its relevance.",
                "Try to use at least two different source providers/institutions for varied perspectives.",
                "Include a brief source analysis at the end of each section.",
                "Make connections between different sources when possible.",
                "When analyzing PDFs, cite the specific page number if available.",
                "If sources are insufficient to address an aspect of the topic, clearly state this limitation rather than attempting to fill the gap."
            ]
        }

    def verify_citations(self, content: str, sources_used: List[int]) -> Dict[str, Any]:
        """
        Enhanced verification of citations in content to ensure every paragraph 
        contains proper citations from the sources_used list.
        
        Args:
            content: The section content to check
            sources_used: List of source IDs that should be cited
                
        Returns:
            Dictionary with verification results
        """
        results = {
            "valid": True,
            "uncited_sources": [],
            "invalid_citations": [],
            "uncited_paragraphs": [],
            "message": ""
        }
        
        # Split content into paragraphs for analysis
        paragraphs = [p for p in content.split('\n\n') if p.strip()]
        
        # Track sources that are cited and paragraphs without citations
        cited_sources = set()
        paragraph_issues = []
        
        # Citation pattern (also matches page number format [id, page X])
        citation_regex = r"\[(\d+)(?:,\s*(?:p\.|page)\s*\d+)?\]"
        
        # Check each paragraph for citations
        for i, paragraph in enumerate(paragraphs):
            if len(paragraph.strip()) < 20:  # Skip very short paragraphs (headers, etc.)
                continue
                
            # Find all citations in this paragraph
            paragraph_citations = [int(match) for match in re.findall(citation_regex, paragraph)]
            
            # Update the set of cited sources
            cited_sources.update(paragraph_citations)
            
            # Check if paragraph has any citations
            if not paragraph_citations:
                results["valid"] = False
                paragraph_issue = {
                    "index": i,
                    "text": paragraph[:100] + "..." if len(paragraph) > 100 else paragraph,
                    "issue": "No citations found"
                }
                paragraph_issues.append(paragraph_issue)
                
            # Check if paragraph cites sources that aren't in sources_used
            invalid_citations = [cite for cite in paragraph_citations if cite not in sources_used]
            if invalid_citations:
                results["valid"] = False
                paragraph_issue = {
                    "index": i,
                    "text": paragraph[:100] + "..." if len(paragraph) > 100 else paragraph,
                    "issue": f"Invalid citations: {invalid_citations}"
                }
                paragraph_issues.append(paragraph_issue)
        
        # Check for sources that should be cited but aren't
        results["uncited_sources"] = [source for source in sources_used if source not in cited_sources]
        if results["uncited_sources"]:
            results["valid"] = False
            
        # Check for sources cited that aren't in sources_used
        results["invalid_citations"] = [cite for cite in cited_sources if cite not in sources_used]
        if results["invalid_citations"]:
            results["valid"] = False
        
        # Store paragraph issues
        results["uncited_paragraphs"] = paragraph_issues
        
        # Create a detailed message
        messages = []
        if results["uncited_sources"]:
            uncited = ", ".join(str(s) for s in results["uncited_sources"])
            messages.append(f"Sources listed but not cited in content: {uncited}")
        
        if results["invalid_citations"]:
            invalid = ", ".join(str(s) for s in results["invalid_citations"])
            messages.append(f"Citations in content not in sources_used list: {invalid}")
            
        if paragraph_issues:
            paragraph_count = len(paragraph_issues)
            messages.append(f"{paragraph_count} paragraphs with citation issues found.")
            
        if messages:
            results["message"] = " ".join(messages)
        else:
            results["message"] = "All citations validated successfully."
        
        return results
    
    def _analyze_provider_diversity(self, sources: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyze the diversity of providers in the sources.
        
        Args:
            sources: List of source dictionaries
            
        Returns:
            Dictionary with provider diversity analysis
        """
        # If no sources, return empty analysis
        if not sources:
            return {
                'diverse_sources': False,
                'total_providers': 0,
                'primary_provider': 'None',
                'provider_distribution': {}
            }
            
        # Count frequency of each provider
        provider_counts = {}
        for source in sources:
            provider = source.get('provider', 'Unknown')
            if provider not in provider_counts:
                provider_counts[provider] = 0
            provider_counts[provider] += 1
        
        # Sort providers by frequency
        sorted_providers = sorted(provider_counts.items(), key=lambda x: x[1], reverse=True)
        
        # Get primary provider (most frequent)
        primary_provider = sorted_providers[0][0] if sorted_providers else 'Unknown'
        
        # Calculate total number of providers
        total_providers = len(provider_counts)
        
        # Determine if sources are diverse (more than one provider)
        diverse_sources = total_providers > 1
        
        return {
            'diverse_sources': diverse_sources,
            'total_providers': total_providers,
            'primary_provider': primary_provider,
            'provider_distribution': provider_counts
        }
        # If no sources, return empty analysis
        if not sources:
            return {
                'diverse_sources': False,
                'total_providers': 0,
                'primary_provider': None,
                'provider_distribution': {}
            }
        
        # Count providers
        provider_counts = {}
        for source in sources:
            provider = source.get('provider', 'Unknown')
            if provider in provider_counts:
                provider_counts[provider] += 1
            else:
                provider_counts[provider] = 1
        
        # Get total number of providers
        total_providers = len(provider_counts)
        
        # Get the primary provider (most common)
        primary_provider = max(provider_counts.items(), key=lambda x: x[1])[0] if provider_counts else None
        
        # Determine if sources are diverse (more than one provider)
        diverse_sources = total_providers > 1
        
        return {
            'diverse_sources': diverse_sources,
            'total_providers': total_providers,
            'primary_provider': primary_provider,
            'provider_distribution': provider_counts
        }
        # If no sources, return empty analysis
        if not sources:
            return {
                'diverse_sources': False,
                'total_providers': 0,
                'primary_provider': None,
                'provider_distribution': {}
            }
            
        # Count providers
        provider_counts = {}
        for source in sources:
            provider = source.get('provider', 'Unknown')
            if provider not in provider_counts:
                provider_counts[provider] = 0
            provider_counts[provider] += 1
            
        # Get total number of providers
        total_providers = len(provider_counts)
        
        # Get primary provider (most common)
        primary_provider = max(provider_counts.items(), key=lambda x: x[1])[0] if provider_counts else None
        
        # Calculate diversity
        diverse_sources = total_providers > 1
        
        return {
            'diverse_sources': diverse_sources,
            'total_providers': total_providers,
            'primary_provider': primary_provider,
            'provider_distribution': provider_counts
        }
        # If no sources, return empty analysis
        if not sources:
            return {
                'diverse_sources': False,
                'total_providers': 0,
                'primary_provider': None,
                'provider_distribution': {}
            }
        
        # Count providers
        provider_counts = {}
        for source in sources:
            provider = source.get('provider', 'Unknown Provider')
            if provider in provider_counts:
                provider_counts[provider] += 1
            else:
                provider_counts[provider] = 1
        
        # Get the provider with the most sources
        primary_provider = max(provider_counts.items(), key=lambda x: x[1])[0] if provider_counts else None
        
        # Check if we have more than one provider
        diverse_sources = len(provider_counts) > 1
        
        return {
            'diverse_sources': diverse_sources,
            'total_providers': len(provider_counts),
            'primary_provider': primary_provider,
            'provider_distribution': provider_counts
        }
        
    def _format_citation(self, record: Dict[str, Any]) -> str:
        """
        Format a record as a citation.
        
        Args:
            record: The record to format
            
        Returns:
            Formatted citation as a string
        """
        # Extract basic metadata
        title = record.get('title', ['Unknown Title'])[0] if isinstance(record.get('title', []), list) else record.get('title', 'Unknown Title')
        creator = record.get('creator', ['Unknown Creator'])[0] if isinstance(record.get('creator', []), list) else record.get('creator', 'Unknown Creator')
        date = record.get('year', 'n.d.')
        
        # Get provider
        provider = record.get('provider', ['Unknown Provider'])[0] if isinstance(record.get('provider', []), list) else record.get('provider', 'Unknown Provider')
        
        # Get URL
        url = ''
        if 'edmIsShownAt' in record:
            if isinstance(record['edmIsShownAt'], list) and record['edmIsShownAt']:
                url = record['edmIsShownAt'][0]
            else:
                url = record['edmIsShownAt']
        
        # Get record type
        doc_type = record.get('type', 'TEXT')
        
        # Format citation based on type
        if doc_type == 'IMAGE':
            return f"{creator}. ({date}). {title} [Image]. {provider}. Retrieved from {url}"
        elif doc_type == 'VIDEO':
            return f"{creator}. ({date}). {title} [Video]. {provider}. Retrieved from {url}"
        elif doc_type == 'SOUND':
            return f"{creator}. ({date}). {title} [Audio]. {provider}. Retrieved from {url}"
        elif doc_type == 'TEXT':
            return f"{creator}. ({date}). {title}. {provider}. Retrieved from {url}"
        else:
            return f"{creator}. ({date}). {title}. {provider}. Retrieved from {url}"


# Tool definition
EUROPEANA_SEQUENTIAL_REPORTING_TOOL = {
    "name": "europeana_sequential_reporting",
    "description": "A tool for generating comprehensive research reports using the Europeana digital library. This tool helps create well-structured, properly cited reports on any topic by breaking the process into sequential steps.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "topic": {
                "type": "string",
                "description": "Research topic for the report (only needed for initialization)"
            },
            "page_count": {
                "type": "integer",
                "description": "Number of pages to generate",
                "minimum": 1,
                "default": 4
            },
            "source_count": {
                "type": "integer",
                "description": "Number of sources to find",
                "minimum": 1,
                "default": 10
            },
            "section_number": {
                "type": "integer",
                "description": "Current section number",
                "minimum": 1
            },
            "total_sections": {
                "type": "integer",
                "description": "Total sections in the report",
                "minimum": 1
            },
            "title": {
                "type": "string",
                "description": "Title of the current section"
            },
            "content": {
                "type": "string",
                "description": "Content of the current section"
            },
            "is_bibliography": {
                "type": "boolean",
                "description": "Whether this section is the bibliography"
            },
            "sources_used": {
                "type": "array",
                "items": {
                    "type": "integer"
                },
                "description": "List of source IDs used in this section"
            },
            "next_section_needed": {
                "type": "boolean",
                "description": "Whether another section is needed"
            },
            "include_graphics": {
                "type": "boolean",
                "description": "Whether to include graphics in the report",
                "default": False
            },
            "confirm_sources": {
                "type": "boolean",
                "description": "Confirmation to proceed with found sources",
                "default": False
            }
        },
        "required": ["section_number", "total_sections", "title", "content", "next_section_needed"]
    }
}


if __name__ == "__main__":
    server = SequentialReportingServer()
    # Add server initialization or test code here
    server.run()