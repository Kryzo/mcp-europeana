# Europeana Sequential Media Documenting

A tool for generating comprehensive research documents about a given topic using Europeana digital library sources.

## Overview

This application allows users to search the extensive digital collections of Europeana (Europe's digital library, museum and archive) and generate comprehensive documents that include metadata, images, videos, audio, and text from various European cultural institutions. The tool focuses on faithfully representing source material without fabricating information.

## Features

- **Advanced Search in Europeana**: Search for documents, books, manuscripts, maps, images, videos, audio recordings and other resources in Europeana's digital collections
- **Multi-Source Documentation**: Gather sources from multiple Europeana providers for diverse perspectives
- **Comprehensive Metadata**: Extract and present detailed metadata from each source
- **Media Links**: Include direct links to images, videos, PDF documents, and audio files
- **PDF Content Extraction**: Extract and analyze text content from PDF documents
- **Bibliography Generation**: Automatically create bibliographic references for all sources
- **Source Diversity Analysis**: Analyze the diversity of sources by provider, type, and content
- **Sequential Report Generation**: Generate well-structured, properly cited reports following an academic format

## Architecture

The application consists of several key components:

1. **Core Components**:
   - `sequential_media_documenting.py`: Main server script that provides the tool functionality
   - `europeana_api/`: Python package for interacting with the Europeana API

2. **Europeana API Module**:
   - `api.py`: Core client for the Europeana API
   - `search.py`: Search utilities for different types of queries
   - `record.py`: Tools for processing and extracting data from Europeana records
   - `config.py`: Configuration constants and settings
   - `sequential_reporting.py`: Tools for generating sequential reports with proper citations

3. **Integration**:
   - MCP (Model Context Protocol) for AI tool functionality
   - Europeana API for accessing Europe's digital cultural heritage

## Europeana API Key

The tool requires a Europeana API key to function properly. Here's how to obtain and use one:

1. **Get a Europeana API key**:
   - Visit the [Europeana API website](https://pro.europeana.eu/page/apis)
   - Register for a free API key
   - The process is straightforward and typically provides immediate access

2. **Using the API key**:
   - You can provide the API key in three ways:
     - Environment variable: `export EUROPEANA_API_KEY=your_key_here`
     - Command line parameter: `--api-key=your_key_here`
     - In the MCP server configuration (see below)

## Model Context Protocol (MCP) Integration

This tool can be integrated with Claude and other AI assistants using the Model Context Protocol (MCP) framework:

### What is Model Context Protocol?

Model Context Protocol (MCP) allows AI assistants like Claude to execute external code and tools, extending their capabilities beyond conversation. MCP provides a standardized way for AI assistants to interact with external systems, access real-time data, and perform actions that aren't possible within the conversation alone.

### Setting up with Claude Desktop

To use this tool with Claude Desktop:

1. **Edit your Claude Desktop configuration**:
   - Locate your `claude_desktop_config.json` file
   - Add the following to the "mcpServers" section:

   ```json
   "mcpServers": {
     "europeana": {
       "command": "py",
       "args": [
         "path\\to\\mcp-europeana\\sequential_media_documenting.py",
         "--api-key=your_europeana_api_key_here"
       ],
       "cwd": "path\\to\\mcp-europeana"
     }
   }
   ```

2. **Replace the following**:
   - `path\\to\\mcp-gdelt` with the actual path to where you cloned this repository
   - `your_europeana_api_key_here` with your Europeana API key

3. **Restart Claude Desktop** to apply the changes

### Using with Claude

Once configured, you can use this tool directly in conversations with Claude by asking it to:

- Research a specific historical topic using Europeana sources
- Find cultural artifacts related to a specific theme
- Generate a comprehensive report on a European historical event
- Locate images, videos, or text documents from European cultural institutions

Claude will use the MCP tool to search Europeana's vast collections and present the information in a well-structured, properly cited document.

## Core Components

### Main Server
- **sequential_media_documenting.py**: Implements the main tool functionality for generating comprehensive documents from Europeana sources

### Europeana API Package
- **api.py**: Core client for interacting with Europeana's search and record APIs
- **search.py**: Search utilities for building different types of Europeana queries
- **record.py**: Tools for processing Europeana records and extracting detailed metadata
- **config.py**: Configuration constants including API URLs and default values
- **sequential_reporting.py**: Framework for generating structured reports with proper citations

## Setup

### Prerequisites
- Python 3.8 or higher
- Europeana API key (as described above)
- Internet connection to access the Europeana API
- PyPDF2 and other dependencies listed in requirements.txt

### Installation

1. Clone the repository:
   ```
   git clone [repository_url]
   cd mcp-gdelt
   ```

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Set your Europeana API key:
   ```
   export EUROPEANA_API_KEY=your_api_key_here
   ```
   Alternatively, you can pass the API key directly when running the tool.

### Running the Tool

1. Start the server with your API key:
   ```
   python sequential_media_documenting.py --api-key=your_api_key_here
   ```

2. For direct queries without starting the server:
   ```
   python sequential_media_documenting.py --direct-query --topic="Your Topic" --count=20 --types TEXT IMAGE
   ```

## Usage

The tool can be used to generate comprehensive documents about any topic using Europeana sources:

1. **Initialize with a topic**: Provide a research topic to search for in Europeana
2. **Search for sources**: The tool will search for relevant sources across Europeana's collections
3. **Extract and analyze content**: For sources with PDF content, the tool will extract and analyze the text
4. **Generate document**: The tool produces a structured document with sources, metadata, and links
5. **Include bibliography**: All sources are properly cited with links to the original material

## Important Notes

- The tool enforces strict content generation rules to prevent fabrication of information
- All information in the generated documents comes directly from Europeana's digital collections
- The tool includes a comprehensive disclaimer explaining the source and nature of the content
- PDF content extraction uses PyPDF2 and is limited to the first few pages for performance reasons

## License

[License information would go here]

## Credits

- Europeana for providing access to Europe's digital cultural heritage
- PyPDF2 for PDF text extraction capabilities
- Anthropic's Claude for AI tool integration capabilities
