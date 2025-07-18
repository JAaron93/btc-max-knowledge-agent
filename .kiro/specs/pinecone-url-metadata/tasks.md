# Implementation Plan

- [x] 1. Update PineconeClient to handle URL metadata in vector operations
  - Modify the `upsert_documents()` method to include URL field in metadata
  - Update the `query_similar()` method to return URL field in results
  - Add URL validation helper method to sanitize and validate URLs
  - Write unit tests for URL metadata handling in vector operations
  - _Requirements: 2.1, 2.2_

- [x] 2. Enhance PineconeAssistantAgent to support URL metadata
  - Update the `upload_documents()` method to include URL in document metadata
  - Modify the `query_assistant()` method to extract and return URL information from citations
  - Add URL formatting in the document structure sent to Pinecone Assistant API
  - Write unit tests for Pinecone Assistant URL metadata integration
  - _Requirements: 2.1, 2.3_

- [x] 3. Update document upload script to include URLs in generated files
  - Modify `upload_to_pinecone_assistant.py` to include URLs in text file headers
  - Format URLs clearly in the generated document structure
  - Ensure backward compatibility with existing upload process
  - Test file generation with URL metadata included
  - _Requirements: 2.1, 4.1_

- [x] 4. Create URL validation and sanitization utilities
  - Implement URL validation function to check format and accessibility
  - Add URL sanitization to handle common formatting issues (missing protocol, etc.)
  - Create helper function to extract domain names for display purposes
  - Write comprehensive tests for URL validation and sanitization
  - _Requirements: 2.2, 4.4_

- [ ] 5. Update query result formatting to include source URLs
  - Modify result formatting functions to include clickable URLs when available
  - Create structured response format that clearly associates content with sources
  - Handle mixed results where some documents have URLs and others don't
  - Add fallback display for documents without URL metadata
  - _Requirements: 1.1, 1.2, 4.1, 4.4_

- [ ] 6. Add URL metadata to existing static documents in data collector
  - Update `collect_bitcoin_basics()` to include relevant URLs for Bitcoin whitepaper and resources
  - Add URLs to `collect_genius_act_info()` for legislative sources
  - Include URLs in `collect_dapp_information()` for educational resources
  - Ensure all static documents have appropriate source URLs where available
  - _Requirements: 2.1, 2.2_

- [ ] 7. Implement error handling for URL-related operations
  - Add graceful handling for documents without URLs in upsert operations
  - Implement retry logic for failed URL validation
  - Create fallback behavior when URL metadata is missing or invalid
  - Add logging for URL-related errors and warnings
  - _Requirements: 2.2, 2.3, 4.4_

- [ ] 8. Create comprehensive tests for URL metadata functionality
  - Write integration tests for end-to-end document processing with URLs
  - Test Pinecone upsert and query operations with URL metadata
  - Create tests for mixed document sets (with and without URLs)
  - Add performance tests for large document uploads with URL metadata
  - _Requirements: 1.1, 2.1, 2.3, 3.1_

- [ ] 9. Update existing documents in Pinecone with URL metadata
  - Create script to identify existing documents that lack URL metadata
  - Implement batch update process to add URLs to existing Pinecone records
  - Use upsert operations to update metadata without losing existing vectors
  - Add progress tracking and error handling for bulk updates
  - _Requirements: 3.1, 3.2, 3.3_

- [ ] 10. Test and validate URL metadata integration with Pinecone Assistant
  - Test document upload to Pinecone Assistant with URL metadata
  - Verify that queries return URL information in assistant responses
  - Test URL display and formatting in the Pinecone Assistant interface
  - Validate that URLs are clickable and lead to correct sources
  - _Requirements: 1.1, 1.3, 4.1, 4.2_