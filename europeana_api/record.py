"""
Record utilities for the Europeana API.
Provides functions to process and extract data from Europeana record objects.
"""

from typing import Dict, Any, List, Optional, Union, Tuple
from .api import EuropeanaAPI
import urllib.parse
import logging
import os
import requests
import tempfile
from PyPDF2 import PdfReader

logger = logging.getLogger(__name__)

class RecordAPI:
    """
    Record utilities for the Europeana API.
    """
    
    def __init__(self, europeana_api: EuropeanaAPI):
        """
        Initialize the Record API.
        
        Args:
            europeana_api: An initialized EuropeanaAPI instance
        """
        self.europeana_api = europeana_api
    def normalize_record_id(self, record_id: str) -> str:
        """Ensure record ID is in the correct format (without leading slash)"""
        return record_id.lstrip('/')

    def get_record(self, record_id: str, file_type: str = 'text') -> Dict[str, Any]:
        try:
            # Strip leading slash if present and ensure consistent format
            record_id = record_id.strip('/')
            
            # Get raw record data first
            record = self.europeana_api.get_record(record_id)
            
            # Return immediately if there's an error
            if record is None or "error" in record:
                return {"error": f"Record not found: {record_id}", "record_id": record_id}
            
            # If no filtering requested, return raw record
            if file_type == 'any':
                return record
                
            # Add better logging
            logging.debug(f"Searching for {file_type} files in record {record_id}")
            
            # If filtering is requested
            if file_type == 'text':
                # Check if record has PDF files in web resources
                if record and 'record' in record:
                    # Track PDF resources
                    pdf_resources = []
                    
                    # Check in aggregations for PDFs
                    aggregations = record['record'].get('aggregations', [])
                    for agg in aggregations:
                        web_resources = agg.get('webResources', [])
                        for resource in web_resources:
                            # Check MIME type
                            mime_type = resource.get('ebucoreHasMimeType', '').lower()
                            url = resource.get('about', '')
                            
                            # Check for PDF by MIME type or file extension
                            if mime_type == 'application/pdf' or url.lower().endswith('.pdf'):
                                pdf_resources.append(resource)
                                
                    # If PDF resources found, attach to record
                    if pdf_resources:
                        record['pdf_resources'] = pdf_resources
                        return record
                    
                    # Also check for PDFs in media links
                    for aggregation in aggregations:
                        for field in ['edmIsShownBy', 'edmIsShownAt', 'edmHasView']:
                            if field in aggregation:
                                url = aggregation[field]
                                if isinstance(url, str) and url.lower().endswith('.pdf'):
                                    record['pdf_url'] = url
                                    return record
                    
                    # If no PDF found, return error
                    return {"error": "No text files found in this record", "record_id": record_id}
            
            return record
        except Exception as e:
            logger.error(f"Error retrieving record {record_id}: {str(e)}")
            return {"error": f"Error retrieving record: {str(e)}", "record_id": record_id}
    
    def process_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a record to extract key information in a more accessible format.
        
        Args:
            record: Raw record data from Europeana API
            
        Returns:
            Processed record with key fields extracted
        """
        if not record or "error" in record:
            return record
        
        # Get the core record object
        obj = record.get("record", {})
        if not obj:
            return record
        
        # Create a processed record
        processed = {
            "id": obj.get("about", ""),
            "metadata": record.get("metadata", {}),
            "title": self.extract_title(obj),
            "creator": self.extract_creator(obj),
            "date": self.extract_date(obj),
            "description": self.extract_description(obj),
            "type": self.extract_type(obj),
            "provider": self.extract_provider(obj),
            "dataProvider": self.extract_data_provider(obj),
            "rights": self.extract_rights(obj),
            "language": self.extract_language(obj),
            "country": self.extract_country(obj),
            "thumbnail": self.europeana_api.extract_thumbnail(obj),
            "isShownBy": self.europeana_api.extract_image_url(obj),
            "isShownAt": self.extract_shown_at(obj),
            "dcTerms": self.extract_dc_terms(obj),
            "edmTerms": self.extract_edm_terms(obj),
            "people": self.extract_agent_entities(obj),
            "places": self.extract_place_entities(obj),
            "concepts": self.extract_concept_entities(obj),
            "timespan": self.extract_timespan_entities(obj),
            "iiif": self.extract_iiif_links(obj),
            "media_links": self.extract_media_links(obj),
            "raw": obj
        }
        
        return processed
    
    def extract_title(self, obj: Dict[str, Any]) -> Optional[Union[str, List[str]]]:
        """Extract title from a record object"""
        # Try proxies first
        for proxy in obj.get("proxies", []):
            if "dcTitle" in proxy:
                titles = []
                for lang, title_list in proxy["dcTitle"].items():
                    titles.extend(title_list)
                if titles:
                    return titles[0] if len(titles) == 1 else titles
        
        # Try europeanaAggregation
        euro_agg = obj.get("europeanaAggregation", {})
        if "edmTitle" in euro_agg:
            titles = []
            for lang, title_list in euro_agg["edmTitle"].items():
                titles.extend(title_list)
            if titles:
                return titles[0] if len(titles) == 1 else titles
        
        return None
    
    def extract_creator(self, obj: Dict[str, Any]) -> Optional[Union[str, List[str]]]:
        """Extract creator from a record object"""
        # Try proxies first
        for proxy in obj.get("proxies", []):
            if "dcCreator" in proxy:
                creators = []
                for lang, creator_list in proxy["dcCreator"].items():
                    creators.extend(creator_list)
                if creators:
                    return creators[0] if len(creators) == 1 else creators
        
        return None
    
    def extract_date(self, obj: Dict[str, Any]) -> Optional[Union[str, List[str]]]:
        """Extract date from a record object"""
        # Try proxies first
        for proxy in obj.get("proxies", []):
            if "dcDate" in proxy:
                dates = []
                for lang, date_list in proxy["dcDate"].items():
                    dates.extend(date_list)
                if dates:
                    return dates[0] if len(dates) == 1 else dates
            
            # Try year field
            if "year" in proxy:
                return proxy["year"][0] if isinstance(proxy["year"], list) and proxy["year"] else proxy["year"]
        
        # Try timespan
        timespan = self.extract_timespan_entities(obj)
        if timespan:
            return timespan[0].get("begin", timespan[0].get("label", None)) if timespan else None
        
        return None
    
    def extract_description(self, obj: Dict[str, Any]) -> Optional[Union[str, List[str]]]:
        """Extract description from a record object"""
        # Try proxies first
        for proxy in obj.get("proxies", []):
            if "dcDescription" in proxy:
                descriptions = []
                for lang, desc_list in proxy["dcDescription"].items():
                    descriptions.extend(desc_list)
                if descriptions:
                    return descriptions[0] if len(descriptions) == 1 else descriptions
        
        return None
    
    def extract_type(self, obj: Dict[str, Any]) -> Optional[str]:
        """Extract type from a record object"""
        # Try proxies for edmType
        for proxy in obj.get("proxies", []):
            if "edmType" in proxy:
                return proxy["edmType"]
        
        return None
    
    def extract_provider(self, obj: Dict[str, Any]) -> Optional[str]:
        """Extract provider from a record object"""
        # Try aggregations
        for agg in obj.get("aggregations", []):
            if "edmProvider" in agg:
                for lang, provider_list in agg["edmProvider"].items():
                    if provider_list:
                        return provider_list[0]
        
        return None
    
    def extract_data_provider(self, obj: Dict[str, Any]) -> Optional[str]:
        """Extract data provider from a record object"""
        # Try aggregations
        for agg in obj.get("aggregations", []):
            if "edmDataProvider" in agg:
                for lang, provider_list in agg["edmDataProvider"].items():
                    if provider_list:
                        return provider_list[0]
        
        return None
    
    def extract_rights(self, obj: Dict[str, Any]) -> Optional[str]:
        """Extract rights from a record object"""
        # Try aggregations
        for agg in obj.get("aggregations", []):
            if "edmRights" in agg:
                if isinstance(agg["edmRights"], dict):
                    for lang, rights_list in agg["edmRights"].items():
                        if rights_list:
                            return rights_list[0]
                elif isinstance(agg["edmRights"], list) and agg["edmRights"]:
                    return agg["edmRights"][0]
                else:
                    return agg["edmRights"]
        
        return None
    
    def extract_language(self, obj: Dict[str, Any]) -> Optional[Union[str, List[str]]]:
        """Extract language from a record object"""
        # Try europeanaAggregation
        euro_agg = obj.get("europeanaAggregation", {})
        if "edmLanguage" in euro_agg:
            if isinstance(euro_agg["edmLanguage"], dict):
                langs = []
                for lang_key, lang_list in euro_agg["edmLanguage"].items():
                    langs.extend(lang_list)
                if langs:
                    return langs[0] if len(langs) == 1 else langs
            else:
                return euro_agg["edmLanguage"]
        
        # Try proxies
        for proxy in obj.get("proxies", []):
            if "dcLanguage" in proxy:
                langs = []
                for lang_key, lang_list in proxy["dcLanguage"].items():
                    langs.extend(lang_list)
                if langs:
                    return langs[0] if len(langs) == 1 else langs
        
        return None
    
    def extract_country(self, obj: Dict[str, Any]) -> Optional[str]:
        """Extract country from a record object"""
        # Try europeanaAggregation
        euro_agg = obj.get("europeanaAggregation", {})
        if "edmCountry" in euro_agg:
            if isinstance(euro_agg["edmCountry"], dict):
                for lang, country_list in euro_agg["edmCountry"].items():
                    if country_list:
                        return country_list[0]
            else:
                return euro_agg["edmCountry"]
        
        return None
    
    def extract_shown_at(self, obj: Dict[str, Any]) -> Optional[str]:
        """Extract edmIsShownAt from a record object"""
        # Try aggregations
        for agg in obj.get("aggregations", []):
            if "edmIsShownAt" in agg:
                if isinstance(agg["edmIsShownAt"], dict):
                    for lang, url_list in agg["edmIsShownAt"].items():
                        if url_list:
                            return url_list[0]
                elif isinstance(agg["edmIsShownAt"], list) and agg["edmIsShownAt"]:
                    return agg["edmIsShownAt"][0]
                else:
                    return agg["edmIsShownAt"]
        
        return None
    
    def extract_dc_terms(self, obj: Dict[str, Any]) -> Dict[str, Any]:
        """Extract Dublin Core terms from a record object"""
        dc_terms = {}
        
        # DC fields to extract
        dc_fields = [
            'title', 'creator', 'subject', 'description', 'publisher',
            'contributor', 'date', 'type', 'format', 'identifier',
            'source', 'language', 'relation', 'coverage', 'rights'
        ]
        
        # Try proxies
        for proxy in obj.get("proxies", []):
            for field in dc_fields:
                dc_key = f"dc{field.capitalize()}"
                if dc_key in proxy:
                    values = []
                    for lang, value_list in proxy[dc_key].items():
                        values.extend(value_list)
                    if values:
                        dc_terms[field] = values[0] if len(values) == 1 else values
        
        return dc_terms
    
    def extract_edm_terms(self, obj: Dict[str, Any]) -> Dict[str, Any]:
        """Extract Europeana Data Model terms from a record object"""
        edm_terms = {}
        
        # EDM fields to extract from aggregations
        edm_fields = [
            'provider', 'dataProvider', 'rights', 'isShownAt', 
            'isShownBy', 'object', 'hasView', 'country', 'language',
            'year', 'ugc'
        ]
        
        # Try aggregations
        for agg in obj.get("aggregations", []):
            for field in edm_fields:
                edm_key = f"edm{field.capitalize()}"
                if edm_key in agg:
                    if isinstance(agg[edm_key], dict):
                        values = []
                        for lang, value_list in agg[edm_key].items():
                            values.extend(value_list)
                        if values:
                            edm_terms[field] = values[0] if len(values) == 1 else values
                    elif isinstance(agg[edm_key], list):
                        edm_terms[field] = agg[edm_key][0] if len(agg[edm_key]) == 1 else agg[edm_key]
                    else:
                        edm_terms[field] = agg[edm_key]
        
        # Try europeanaAggregation
        euro_agg = obj.get("europeanaAggregation", {})
        for field in edm_fields:
            edm_key = f"edm{field.capitalize()}"
            if edm_key in euro_agg:
                if isinstance(euro_agg[edm_key], dict):
                    values = []
                    for lang, value_list in euro_agg[edm_key].items():
                        values.extend(value_list)
                    if values:
                        edm_terms[field] = values[0] if len(values) == 1 else values
                elif isinstance(euro_agg[edm_key], list):
                    edm_terms[field] = euro_agg[edm_key][0] if len(euro_agg[edm_key]) == 1 else euro_agg[edm_key]
                else:
                    edm_terms[field] = euro_agg[edm_key]
        
        return edm_terms
    
    def extract_agent_entities(self, obj: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract agent (people, organizations) entities from a record object"""
        agents = []
        
        # Look for Agent entities in the contextual entity section
        for entity in obj.get("agents", []):
            agent = {
                "id": entity.get("about", ""),
                "prefLabel": self._extract_multilingual_value(entity, "prefLabel"),
                "altLabel": self._extract_multilingual_value(entity, "altLabel"),
                "note": self._extract_multilingual_value(entity, "note"),
                "begin": entity.get("begin", ""),
                "end": entity.get("end", ""),
                "type": "Agent"
            }
            agents.append(agent)
        
        return agents
    
    def extract_place_entities(self, obj: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract place entities from a record object"""
        places = []
        
        # Look for Place entities in the contextual entity section
        for entity in obj.get("places", []):
            place = {
                "id": entity.get("about", ""),
                "prefLabel": self._extract_multilingual_value(entity, "prefLabel"),
                "altLabel": self._extract_multilingual_value(entity, "altLabel"),
                "note": self._extract_multilingual_value(entity, "note"),
                "latitude": entity.get("latitude", ""),
                "longitude": entity.get("longitude", ""),
                "type": "Place"
            }
            places.append(place)
        
        return places
    
    def extract_concept_entities(self, obj: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract concept entities from a record object"""
        concepts = []
        
        # Look for Concept entities in the contextual entity section
        for entity in obj.get("concepts", []):
            concept = {
                "id": entity.get("about", ""),
                "prefLabel": self._extract_multilingual_value(entity, "prefLabel"),
                "altLabel": self._extract_multilingual_value(entity, "altLabel"),
                "note": self._extract_multilingual_value(entity, "note"),
                "type": "Concept"
            }
            concepts.append(concept)
        
        return concepts
    
    def extract_timespan_entities(self, obj: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract timespan entities from a record object"""
        timespans = []
        
        # Look for Timespan entities in the contextual entity section
        for entity in obj.get("timespans", []):
            timespan = {
                "id": entity.get("about", ""),
                "prefLabel": self._extract_multilingual_value(entity, "prefLabel"),
                "altLabel": self._extract_multilingual_value(entity, "altLabel"),
                "note": self._extract_multilingual_value(entity, "note"),
                "begin": entity.get("begin", ""),
                "end": entity.get("end", ""),
                "type": "Timespan"
            }
            timespans.append(timespan)
        
        return timespans
    
    def extract_iiif_links(self, obj: Dict[str, Any]) -> Dict[str, Any]:
        """Extract IIIF manifest and service links from a record object"""
        iiif_data = {
            "hasManifest": False,
            "manifestUrl": None,
            "services": []
        }
        
        # Try to find IIIF manifest in webResources
        for agg in obj.get("aggregations", []):
            if "webResources" in agg:
                for resource in agg["webResources"]:
                    # Look for IIIF service
                    if "svcsHasService" in resource:
                        service_urls = resource["svcsHasService"]
                        if isinstance(service_urls, list):
                            for service_url in service_urls:
                                iiif_data["services"].append({
                                    "url": service_url,
                                    "resourceUrl": resource.get("about", "")
                                })
                        else:
                            iiif_data["services"].append({
                                "url": service_urls,
                                "resourceUrl": resource.get("about", "")
                            })
                    
                    # Look for manifest
                    if "dctermsIsReferencedBy" in resource:
                        ref_urls = resource["dctermsIsReferencedBy"]
                        for url in (ref_urls if isinstance(ref_urls, list) else [ref_urls]):
                            if "manifest" in url.lower() and "/iiif/" in url.lower():
                                iiif_data["hasManifest"] = True
                                iiif_data["manifestUrl"] = url
                                break
        
        return iiif_data

    def extract_media_links(self, obj: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract media links from a record object with MIME type detection.
        
        Args:
            obj: The record object dictionary
            
        Returns:
            List of media links with their metadata
        """
        media_links = []
        
        # Mapping of common file extensions to MIME types
        mime_type_mapping = {
            '.pdf': 'application/pdf',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.mp3': 'audio/mpeg',
            '.wav': 'audio/wav',
            '.mp4': 'video/mp4',
            '.mpeg': 'video/mpeg',
            '.mov': 'video/quicktime'
        }
        
        # Extract media from aggregations
        for agg in obj.get("aggregations", []):
            # edmIsShownBy (primary media representation)
            if "edmIsShownBy" in agg:
                media_url = agg["edmIsShownBy"]
                ext = os.path.splitext(media_url)[1].lower()
                mime_type = mime_type_mapping.get(ext, 'application/octet-stream')
                
                media_links.append({
                    "url": media_url,
                    "type": "primary",
                    "mime_type": mime_type
                })
            
            # Check for webResources
            if "webResources" in agg:
                for resource in agg["webResources"]:
                    if "about" in resource:
                        resource_url = resource["about"]
                        ext = os.path.splitext(resource_url)[1].lower()
                        mime_type = mime_type_mapping.get(ext, 'application/octet-stream')
                        
                        # Additional metadata if available
                        media_info = {
                            "url": resource_url,
                            "type": "web_resource",
                            "mime_type": mime_type
                        }
                        
                        # Add additional metadata if present
                        if "dcFormat" in resource:
                            media_info["format"] = resource["dcFormat"]
                        
                        media_links.append(media_info)
        
        return media_links
    
    def _extract_multilingual_value(self, entity: Dict[str, Any], field_name: str) -> Dict[str, List[str]]:
        """Helper method to extract multilingual values from an entity"""
        result = {}
        
        if field_name in entity:
            for lang, values in entity[field_name].items():
                if isinstance(values, list):
                    result[lang] = values
                else:
                    result[lang] = [values]
        
        return result
        
    def extract_pdf_content(
        self, 
        record_id: str = None, 
        pdf_url: str = None, 
        page_range: Tuple[int, int] = None, 
        max_pages: int = 50
    ) -> Dict[str, Any]:
        """
        Extract text content from a PDF associated with a Europeana record.
        
        Args:
            record_id: Europeana record ID to find PDF from
            pdf_url: Direct URL to PDF (alternative to record_id)
            page_range: Optional tuple of (start_page, end_page) to limit extraction
            max_pages: Maximum number of pages to extract to prevent excessive processing
            
        Returns:
            Dictionary with extracted text and metadata
        """
        # If record_id is provided, first get the record to find PDF URL
        if record_id and not pdf_url:
            record_data = self.get_record(record_id)
            if "error" in record_data:
                return record_data
                
            processed_record = self.process_record(record_data)
            
            # Find PDF URL in media_links
            for link in processed_record.get('media_links', []):
                mime_type = link.get('mime_type', '').lower()
                url = link.get('url', '')
                if mime_type == 'application/pdf' or url.lower().endswith('.pdf'):
                    pdf_url = url
                    break
            
            # Also check in webResources if available
            if not pdf_url and "raw" in processed_record:
                for agg in processed_record["raw"].get("aggregations", []):
                    for resource in agg.get("webResources", []):
                        mime_type = resource.get("ebucoreHasMimeType", "").lower()
                        if mime_type == "application/pdf":
                            pdf_url = resource.get("about", "")
                            break
        
        if not pdf_url:
            return {
                "error": "No PDF found for this record",
                "record_id": record_id
            }
        
        try:
            # Download the PDF
            logger.info(f"Downloading PDF from: {pdf_url}")
            response = requests.get(pdf_url, stream=True, timeout=30)
            if response.status_code != 200:
                return {
                    "error": f"Failed to download PDF: HTTP {response.status_code}",
                    "url": pdf_url
                }
            
            # Save temporarily
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_file:
                temp_path = temp_file.name
                temp_file.write(response.content)
            
            # Extract text from PDF
            result = {
                "success": False,
                "text": [],
                "source": pdf_url,
                "record_id": record_id,
                "pages": 0,
                "total_pages": 0
            }
            
            try:
                # Use PyPDF2 to extract text
                pdf = PdfReader(temp_path)
                result["total_pages"] = len(pdf.pages)
                
                # Determine page range to extract
                start_page = 0
                end_page = min(len(pdf.pages), max_pages)
                
                if page_range:
                    start_page = max(0, page_range[0] - 1)  # Convert from 1-indexed to 0-indexed
                    end_page = min(len(pdf.pages), page_range[1])
                
                # Extract text from each page
                page_texts = []
                for i in range(start_page, end_page):
                    page = pdf.pages[i]
                    text = page.extract_text()
                    if text.strip():
                        page_texts.append({
                            "page_number": i + 1,
                            "content": text
                        })
                
                result["text"] = page_texts
                result["pages"] = len(page_texts)
                result["success"] = len(page_texts) > 0
                
                # Extract basic metadata
                if hasattr(pdf, 'metadata') and pdf.metadata:
                    metadata = {}
                    for key, value in pdf.metadata.items():
                        if key and value:
                            clean_key = key.strip('/').lower()
                            metadata[clean_key] = value
                    result["pdf_metadata"] = metadata
                
                return result
                
            except Exception as e:
                logger.error(f"Error extracting PDF content: {str(e)}")
                return {
                    "error": f"Failed to extract PDF content: {str(e)}",
                    "url": pdf_url
                }
                
        except Exception as e:
            logger.error(f"Error processing PDF: {str(e)}")
            return {
                "error": f"Failed to process PDF: {str(e)}",
                "url": pdf_url
            }
            
        finally:
            # Clean up temp file
            try:
                if 'temp_path' in locals():
                    os.unlink(temp_path)
            except Exception as e:
                logger.warning(f"Failed to delete temporary file: {str(e)}")