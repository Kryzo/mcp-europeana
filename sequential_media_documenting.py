#!/usr/bin/env python
"""
Europeana Sequential Media Documenting Server
---------------------------------------------
This server provides a tool to generate comprehensive documents 
about a given topic using Europeana sources.
"""

import sys
import argparse
import os
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from mcp.server.fastmcp import FastMCP
from europeana_api import EuropeanaAPI, SearchAPI, RecordAPI
from europeana_api.config import DEFAULT_MAX_RESULTS

# Configure more detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("europeana_media_documenting_server.log"),
        logging.StreamHandler(sys.stderr)  # Ensure logging to stderr
    ]
)
logger = logging.getLogger(__name__)

# Global API key that can be set programmatically or via CLI
GLOBAL_API_KEY = None

# Initialize MCP server
try:
    mcp = FastMCP("europeana-media-documenting")
except Exception as e:
    logger.error(f"Failed to initialize MCP server: {e}")
    sys.exit(1)

@mcp.tool()
def sequential_media_documenting(
    topic: str,
    source_count: int = 20,
    include_types: List[str] = None,
    additional_filters: List[str] = None
) -> Dict[str, Any]:
    """
    Generate a comprehensive document about a given topic using Europeana sources.
    
    Args:
        topic: The subject to research
        source_count: Number of sources to find (default: 20)
        include_types: List of document types to include (e.g., ['TEXT', 'IMAGE', 'VIDEO'])
        additional_filters: Additional search filters to refine results
    
    Returns:
        Comprehensive document with sources, metadata, and analysis
    """
    # Validate inputs
    if not topic:
        return {"error": "A topic must be specified"}
    
    # Initialize API clients with priority: 
    # 1. Global API key (set programmatically)
    # 2. Environment variable
    # 3. Default value (fallback for testing)
    global GLOBAL_API_KEY
    api_key = GLOBAL_API_KEY or os.environ.get('EUROPEANA_API_KEY') or "your_api_key"  # Fallback for testing
    
    logger.debug(f"Using API key: {api_key[:3]}...{api_key[-3:]} (masked for security)")
    
    try:
        europeana_api = EuropeanaAPI(api_key)
        search_api = SearchAPI(europeana_api)
        record_api = RecordAPI(europeana_api)
    except Exception as e:
        logger.error(f"Failed to initialize Europeana API clients: {e}")
        return {"error": f"API initialization failed: {e}"}
    
    # Prepare search filters
    filters = additional_filters or []
    
    # Add type filters if specified
    if include_types:
        type_filters = [f"TYPE:{doc_type.upper()}" for doc_type in include_types]
        filters.extend(type_filters)
    
    # Perform advanced search
    try:
        logger.debug(f"Performing search for topic: '{topic}' with filters: {filters}")
        search_results = search_api.advanced_search(
            query=topic,
            rows=source_count,
            filters=filters
        )
        logger.debug(f"Search completed. Results: {bool(search_results)}")
        logger.debug(f"Raw search results keys: {search_results.keys() if isinstance(search_results, dict) else 'Not a dict'}")
        
        # Check for records/items keys in results (depending on API response format)
        items = []
        if isinstance(search_results, dict):
            if 'items' in search_results:
                items = search_results.get('items', [])
                logger.debug(f"Found {len(items)} items in 'items' key")
            elif 'records' in search_results:
                items = search_results.get('records', [])
                logger.debug(f"Found {len(items)} items in 'records' key")
            elif 'raw_response' in search_results and isinstance(search_results['raw_response'], dict):
                raw = search_results['raw_response']
                logger.debug(f"Examining raw_response with keys: {raw.keys()}")
                if 'items' in raw:
                    items = raw.get('items', [])
                    logger.debug(f"Found {len(items)} items in raw_response['items']")
            
            # Debug first item if available
            if items and len(items) > 0:
                logger.debug(f"First item keys: {items[0].keys() if isinstance(items[0], dict) else 'Not a dict'}")
        
        logger.debug(f"Final items count: {len(items)}")
    except Exception as e:
        logger.error(f"Search failed: {e}")
        return {"error": f"Search failed: {e}"}
    
    # Process search results
    sources_details = []
    type_counts = {}
    total_media_details = {}
    
    # Process each item in search results
    for item in items:
        try:
            # Get full record details
            record_id = item.get('id', '')
            logger.debug(f"Getting record details for ID: {record_id}")
            
            # Use file_type='any' to get all types, not just text files
            record = record_api.get_record(record_id, file_type='any')
            
            if not record or "error" in record:
                logger.warning(f"Skip record {record_id}: {record.get('error') if record else 'No record returned'}")
                continue
            
            # Process the record
            processed_record = record_api.process_record(record)
            
            # Prepare source details
            source_info = {
                "id": processed_record.get('id', 'N/A'),
                "title": processed_record.get('title', 'Untitled'),
                "type": processed_record.get('type', 'Unknown'),
                "provider": processed_record.get('provider', 'Unknown'),
                "date": processed_record.get('date', 'N/A'),
                "description": processed_record.get('description', 'No description available'),
                "rights": processed_record.get('rights', 'No rights information')
            }
            
            # Handle source URL, with special format for INA sources
            source_url = processed_record.get('isShownAt', 'No URL available')
            
            # Special handling for INA sources
            if 'ina.fr' in source_url.lower():
                # Check if we can extract the identifier
                ina_id = None
                
                # Try to extract from the ID field in metadata
                if processed_record.get('raw', {}).get('proxies'):
                    for proxy in processed_record.get('raw', {}).get('proxies', []):
                        if proxy.get('dcIdentifier', {}).get('def'):
                            ina_id = proxy.get('dcIdentifier', {}).get('def')[0]
                            break
                
                # If not found in metadata, try to extract from URL
                if not ina_id and '/video/' in source_url:
                    parts = source_url.split('/video/')
                    if len(parts) > 1:
                        ina_id = parts[1].split('/')[0].replace('.fr.html', '').replace('.html', '')
                
                # If identifier found, create new URL format
                if ina_id:
                    source_info['source_url'] = f"https://www.ina.fr/ina-eclaire-actu/video/{ina_id.lower()}"
                    # Store the original identifier for reference
                    source_info['identifier'] = ina_id
                else:
                    source_info['source_url'] = source_url
            else:
                source_info['source_url'] = source_url
            
            # Count source types
            source_type = source_info['type']
            type_counts[source_type] = type_counts.get(source_type, 0) + 1
            
            # Extract media details
            media_links = processed_record.get('media_links', [])
            
            # For INA sources, only process video links and ignore images
            is_ina_source = False
            source_provider = str(source_info.get('provider', '')).lower()
            source_url = str(source_info.get('source_url', '')).lower()
            
            if 'ina' in source_provider or 'ina.fr' in source_url:
                is_ina_source = True
                # If this is an INA source and we have the identifier, add a direct video link
                if 'identifier' in source_info:
                    ina_id = source_info['identifier'].lower()
                    video_info = {
                        "url": f"https://www.ina.fr/ina-eclaire-actu/video/{ina_id}",
                        "mime_type": "video/mp4",
                        "source_title": source_info['title'],
                        "provider": "INA",
                        "identifier": ina_id
                    }
                    if source_info['id'] not in total_media_details:
                        total_media_details[source_info['id']] = []
                    total_media_details[source_info['id']].append(video_info)
            
            # Process regular media links if not INA or if we should process all media
            if not is_ina_source:
                for media in media_links:
                    mime_type = media.get('mime_type', '').lower()
                    media_info = {
                        "url": media.get('url', ''),
                        "mime_type": mime_type,
                        "source_title": source_info['title']
                    }
                    
                    # Categorize media
                    if 'image' in mime_type:
                        if source_info['id'] not in total_media_details:
                            total_media_details[source_info['id']] = []
                        total_media_details[source_info['id']].append(media_info)
                    elif 'pdf' in mime_type:
                        # Try to extract PDF content if possible
                        pdf_content = record_api.extract_pdf_content(pdf_url=media_info['url'], max_pages=3)
                        media_info['text_preview'] = pdf_content.get('text', [])
                        if source_info['id'] not in total_media_details:
                            total_media_details[source_info['id']] = []
                        total_media_details[source_info['id']].append(media_info)
                    elif 'video' in mime_type:
                        if source_info['id'] not in total_media_details:
                            total_media_details[source_info['id']] = []
                        total_media_details[source_info['id']].append(media_info)
                    elif 'audio' in mime_type:
                        if source_info['id'] not in total_media_details:
                            total_media_details[source_info['id']] = []
                        total_media_details[source_info['id']].append(media_info)
                    else:
                        if source_info['id'] not in total_media_details:
                            total_media_details[source_info['id']] = []
                        total_media_details[source_info['id']].append(media_info)
            
            # Add source details
            sources_details.append(source_info)
        
        except Exception as e:
            logger.warning(f"Error processing record: {e}")
    
    # Prepare final document with strict instructions for AI
    document = {
        "topic": topic,
        "search_metadata": {
            "total_results": len(items),
            "search_date": datetime.now().isoformat(),
            "source_count": source_count,
            "include_types": include_types,
            "additional_filters": additional_filters,
            "instructions": {
                "content_generation": "Strictly prohibited",
                "allowed_actions": [
                    "Report only information directly from Europeana search results",
                    "Do not generate any additional content or analysis",
                    "Do not use any external knowledge or information",
                    "Do not invent or extrapolate any information",
                    "Only use exact metadata and links provided in the results"
                ],
                "format_requirements": {
                    "structure": "Must maintain exact structure of search results",
                    "metadata": "Must preserve all original metadata fields",
                    "links": "Must use only URLs provided in search results",
                    "dates": "Must use exact dates from search results"
                }
            },
            "document_generation_instructions": {
                "step_by_step": [
                    {
                        "step": 1,
                        "action": "Read search results",
                        "description": "Read ONLY the information provided in the search results array",
                        "rules": [
                            "Do not read any external sources",
                            "Do not use any prior knowledge",
                            "Only use information from the search results"
                        ]
                    },
                    {
                        "step": 2,
                        "action": "Create document structure",
                        "description": "Create a document with ONLY the following sections",
                        "sections": [
                            {
                                "name": "Search Metadata",
                                "fields": ["total_results", "search_date", "source_count", "include_types"]
                            },
                            {
                                "name": "Findings",
                                "fields": ["type", "title", "provider", "date", "description", "rights", "source_url", "media"]
                            },
                            {
                                "name": "Bibliography",
                                "fields": ["by_type", "summary"]
                            }
                        ]
                    },
                    {
                        "step": 3,
                        "action": "Populate content",
                        "description": "Fill each section with EXACT content from search results",
                        "rules": [
                            "Copy text EXACTLY as it appears in search results",
                            "Do not modify or interpret dates",
                            "Do not translate titles",
                            "Preserve all original URLs"
                        ]
                    },
                    {
                        "step": 4,
                        "action": "Validate content",
                        "description": "Ensure all content matches search results",
                        "checks": [
                            "Compare each field with original search results",
                            "Verify no additional content was added",
                            "Confirm no modifications were made"
                        ]
                    }
                ],
                "prohibited_actions": [
                    "Generating any additional text",
                    "Adding analysis or interpretation",
                    "Creating summaries or conclusions",
                    "Using external knowledge",
                    "Modifying original content",
                    "Translating or interpreting text",
                    "Adding personal opinions",
                    "Creating new sections or categories"
                ]
            }
        },
        "findings": [],
        "bibliography": {
            "by_type": {},
            "summary": {
                "total_sources": len(sources_details),
                "source_types": type_counts
            }
        }
    }

    # Add strict processing instructions
    processing_instructions = {
        "content_extraction": {
            "rules": [
                "Extract only exact text from metadata fields",
                "Preserve all original formatting and special characters",
                "Do not modify or interpret dates",
                "Do not translate or modify titles",
                "Preserve all original URLs without modification"
            ],
            "validation": {
                "required_fields": ["type", "title", "provider", "date", "description", "rights", "source_url"],
                "url_validation": "Must be exact URLs from Europeana results",
                "date_format": "Preserve original date format from results"
            }
        },
        "media_handling": {
            "rules": [
                "Use only media links provided in search results",
                "Preserve original mime types",
                "Do not generate or modify media content",
                "Maintain original source titles"
            ]
        }
    }

    # Process each source with strict validation
    for source in sources_details:
        # Validate source data
        if not all(field in source for field in processing_instructions["content_extraction"]["validation"]["required_fields"]):
            logger.warning(f"Source missing required fields: {source}")
            continue

        # Extract and validate media
        media = []
        if source.get('id') in total_media_details:
            for media_item in total_media_details[source['id']]:
                if not media_item.get('url') or not media_item.get('mime_type'):
                    logger.warning(f"Invalid media item: {media_item}")
                    continue
                media.append(media_item)

        # Create finding with strict validation
        finding = {
            "type": source.get('type', 'Unknown'),
            "title": source.get('title', 'Untitled'),
            "provider": source.get('provider', 'Unknown'),
            "date": source.get('date', 'N/A'),
            "description": source.get('description', 'No description available'),
            "rights": source.get('rights', 'No rights information'),
            "source_url": source.get('source_url', 'No URL available'),
            "media": media
        }

        # Validate finding before adding
        if all(field in finding for field in processing_instructions["content_extraction"]["validation"]["required_fields"]):
            document['findings'].append(finding)

            # Update bibliography by type
            source_type = source.get('type', 'Unknown')
            if source_type not in document['bibliography']['by_type']:
                document['bibliography']['by_type'][source_type] = []
            document['bibliography']['by_type'][source_type].append({
                "title": source.get('title', 'Untitled'),
                "url": source.get('source_url', 'No URL available'),
                "date": source.get('date', 'N/A')
            })
        else:
            logger.warning(f"Incomplete finding: {finding}")

    # Add strict enforcement rules
    document['enforcement_rules'] = {
        "content_generation": {
            "prohibited": True,
            "validation": {
                "no_additional_text": True,
                "no_synthesis": True,
                "no_analysis": True,
                "no_inference": True
            }
        },
        "data_integrity": {
            "preserve_original": True,
            "no_modification": True,
            "no_translation": True,
            "no_interpretation": True
        },
        "link_handling": {
            "strict_validation": True,
            "no_external_links": True,
            "preserve_original_urls": True
        }
    }

    # Add comprehensive disclaimer
    document['disclaimer'] = {
        "content": (
            "This document contains ONLY information and links that were directly found in the Europeana search results. "
            "No additional content or analysis has been generated beyond what was explicitly provided by the Europeana API. "
            "All dates, titles, descriptions, and URLs are exact copies from the search results. "
            "No content has been modified, translated, or interpreted."
        ),
        "enforcement": {
            "strict": True,
            "validation": True,
            "no_exceptions": True
        },
        "generation_instructions": {
            "step_by_step": [
                "always provide links for each part",
                "links should be clickable",
                "Read ONLY the search results array",
                "Only use the information that is provided here and never add your won data to it",
                "Do NOT add any additional information",
                "Do NOT modify any content",
                "You can interpret and analyze the information provided but you can not augment it with oyour own thought",
                "Follow the original formatting but make it more readable"
            ],
            "validation_rules": [
                "Compare each field with original search results",
                "Verify no additional content",
                "Confirm no modifications"
            ]
        }
    }

    logger.debug(f"Document prepared. Total sources: {len(sources_details)}")
    return document


def set_api_key(key: str):
    """
    Set the global API key programmatically. 
    This allows the function to be called directly with a predefined API key.
    """
    global GLOBAL_API_KEY
    GLOBAL_API_KEY = key
    logger.info(f"API key set programmatically: {key[:3]}...{key[-3:]} (masked for security)")


def main():
    """
    Main entry point for the Europeana Media Documenting Server.
    """
    parser = argparse.ArgumentParser(description="Europeana Media Documenting Server")
    parser.add_argument("--api-key", help="Europeana API key (can also be set via EUROPEANA_API_KEY environment variable)")
    parser.add_argument("--direct-query", help="Run a direct query without starting the server", action="store_true")
    parser.add_argument("--topic", help="Topic to search for when using direct-query")
    parser.add_argument("--count", type=int, default=10, help="Number of sources to find when using direct-query")
    parser.add_argument("--types", nargs='+', help="Document types to include (e.g., TEXT IMAGE VIDEO) when using direct-query")
    
    try:
        args = parser.parse_args()
        
        # Set the global API key if provided
        if args.api_key:
            set_api_key(args.api_key)
        
        # Handle direct query mode
        if args.direct_query:
            if not args.topic:
                print("Error: --topic is required with --direct-query")
                sys.exit(1)
            
            # Run the function directly
            result = sequential_media_documenting(
                topic=args.topic,
                source_count=args.count,
                include_types=args.types
            )
            
            # Print result as JSON
            import json
            print(json.dumps(result, indent=2))
            return
        
        # Normal server mode
        logger.info("Starting Europeana Media Documenting Server")
        
        # Run the MCP server
        try:
            mcp.run()
        except Exception as e:
            logger.error(f"MCP server failed to run: {e}")
            sys.exit(1)
    
    except Exception as e:
        logger.error(f"Server initialization failed: {e}")
        sys.exit(1)


# Support direct importation and usage without command-line
if __name__ == "__main__":
    main()
