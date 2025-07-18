# Design Document

## Overview

This design enhances the Bitcoin knowledge agent by implementing URL metadata storage in Pinecone vector database. The solution will modify existing document processing workflows to include source URLs as metadata, update the Pinecone Assistant integration to handle URL metadata, and enhance the retrieval system to return source URLs with responses.

The design leverages Pinecone's built-in metadata capabilities to store URLs alongside document vectors, ensuring that users receive proper source attribution when the AI retrieves information.

## Architecture

### Current Architecture
- **Data Collection**: `BitcoinDataCollector` gathers documents from RSS feeds and static sources
- **Document Processing**: Documents are structured with title, content, source, and category
- **Pinecone Integration**: Two approaches exist:
  - Direct Pinecone client (`PineconeClient`) for vector operations
  - Pinecone Assistant API (`PineconeAssistantAgent`) for managed assistant functionality
- **Upload Process**: Documents are converted to text files for manual upload to Pinecone Assistant

### Enhanced Architecture
The enhanced system will maintain the same overall structure while adding URL metadata support:

```
Data Sources → Data Collector → Document Processor → Pinecone Storage
     ↓              ↓               ↓                    ↓
RSS Feeds      Extract URLs    Add URL Metadata    Store with Vectors
Static Data    Validate URLs   Format for Upload   Include in Queries
```

## Components and Interfaces

### 1. Document Structure Enhancement

**Current Document Format:**
```python
{
    'id': str,
    'title': str,
    'content': str,
    'source': str,
    'category': str
}
```

**Enhanced Document Format:**
```python
{
    'id': str,
    'title': str,
    'content': str,
    'source': str,
    'category': str,
    'url': str,  # New field
    'published': str  # Optional, already exists for RSS
}
```

### 2. Pinecone Metadata Schema

**Enhanced Metadata Structure:**
```python
{
    'title': str,
    'source': str,
    'category': str,
    'content': str,  # Truncated content for metadata
    'url': str,      # New field for source URL
    'published': str  # Optional publication date
}
```

### 3. Data Collector Modifications

**BitcoinDataCollector Enhancements:**
- Ensure all RSS articles include the `url` field (already implemented)
- Add URL fields to static documents where applicable
- Validate URL formats before processing
- Handle missing URLs gracefully

### 4. Pinecone Client Updates

**PineconeClient Enhancements:**
- Update `upsert_documents()` method to include URL in metadata
- Modify `query_similar()` method to return URL in results
- Add URL validation and sanitization

### 5. Pinecone Assistant Integration

**PineconeAssistantAgent Enhancements:**
- Update `upload_documents()` method to include URL in metadata
- Ensure `query_assistant()` method returns URL information in citations
- Handle URL metadata in document formatting

### 6. Upload Process Improvements

**File Generation Updates:**
- Include URLs in generated text files for manual upload
- Format URLs clearly in document headers
- Maintain backward compatibility with existing uploads

## Data Models

### Document Model
```python
class Document:
    id: str
    title: str
    content: str
    source: str
    category: str
    url: Optional[str] = None
    published: Optional[str] = None
    
    def to_pinecone_format(self) -> Dict[str, Any]:
        """Convert to Pinecone upsert format with metadata"""
        return {
            'id': self.id,
            'metadata': {
                'title': self.title,
                'source': self.source,
                'category': self.category,
                'content': self.content[:1000],
                'url': self.url or '',
                'published': self.published or ''
            }
        }
```

### Query Result Model
```python
class QueryResult:
    id: str
    score: float
    title: str
    source: str
    category: str
    content: str
    url: Optional[str] = None
    
    def format_with_source(self) -> str:
        """Format result with source attribution"""
        result = f"**{self.title}**\n{self.content}"
        if self.url:
            result += f"\n\n*Source: [{self.source}]({self.url})*"
        else:
            result += f"\n\n*Source: {self.source}*"
        return result
```

## Error Handling

### URL Validation
- **Invalid URLs**: Log warning and continue processing without URL
- **Missing URLs**: Handle gracefully, don't fail document processing
- **Malformed URLs**: Attempt to fix common issues (missing protocol, etc.)

### Pinecone Operations
- **Metadata Size Limits**: Truncate URLs if they exceed Pinecone limits
- **Upsert Failures**: Retry without URL metadata if upsert fails
- **Query Failures**: Return results without URLs rather than failing completely

### Backward Compatibility
- **Existing Documents**: Support documents without URL metadata
- **Mixed Results**: Handle query results where some documents have URLs and others don't
- **Legacy Uploads**: Continue to work with previously uploaded documents

## Testing Strategy

### Unit Tests
1. **Document Processing Tests**
   - Test URL extraction from RSS feeds
   - Test URL validation and sanitization
   - Test document format conversion

2. **Pinecone Integration Tests**
   - Test metadata inclusion in upserts
   - Test URL retrieval in queries
   - Test error handling for malformed URLs

3. **Data Collector Tests**
   - Test RSS feed processing with URLs
   - Test static document URL assignment
   - Test missing URL handling

### Integration Tests
1. **End-to-End Upload Tests**
   - Test complete document upload with URLs
   - Test Pinecone Assistant integration
   - Test file generation with URL metadata

2. **Query Tests**
   - Test retrieval with URL metadata
   - Test response formatting with source links
   - Test mixed results (with and without URLs)

### Manual Testing
1. **Pinecone Assistant UI**
   - Upload documents and verify URL metadata appears
   - Query assistant and verify URLs are returned
   - Test clicking on returned URLs

2. **MCP Tool Testing**
   - Test MCP queries return URL metadata
   - Verify URL formatting in responses
   - Test error handling for missing URLs

## Implementation Phases

### Phase 1: Core Infrastructure
- Update document models to include URL field
- Modify PineconeClient to handle URL metadata
- Update data collector to ensure URL extraction

### Phase 2: Pinecone Assistant Integration
- Update PineconeAssistantAgent for URL metadata
- Modify upload scripts to include URLs
- Test with Pinecone Assistant API

### Phase 3: Response Enhancement
- Update query result formatting to include URLs
- Enhance MCP tool responses with source links
- Add URL validation and error handling

### Phase 4: Testing and Validation
- Comprehensive testing of all components
- Manual testing with Pinecone Assistant UI
- Performance testing with large document sets