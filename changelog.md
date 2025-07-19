# Changelog

All notable changes to this project will be documented in this file.

## Known Issues/Roadmap:
- Developing a better document parser with cleaned up text such as header/footer removal and non-helpful text. Formats are a bit weird. (Long-term)
- Metadata is lacking. Building out better metadata. (Long-term)

## [1.0.3] - 2025-07-18
### Added
- Document catalog viewer

## [1.0.2] - 2025-07-11
### Changed
- Updated langchain imports and changed deprecated classes
- Changed number of references from 10 to 15.

## [1.0.1] - 2025-07-09
### Changed
- Added known issues section.
- Changed system prompt to ensure responses are in English.
- Increased number of documents queried.

## [1.0.1] - 2025-06-30
### Added
- Google authentication and Astra DB used for authentication
- Added tracking queries

### Changed
- Moved reset button to chat page only
- Authentication based on database query and Google Auth
- Changed number of references from 4 to 10


## [1.0.0] - 2025-06-29
### Added
- Initial release of ClerkGPT chat app.
- User authentication via secrets and Google Authentication.
- Conversational memory with LangChain.
- Reference rendering for source documents.
- Reset conversation button
- Added caching of vector store
- Added 52nd GA documents

### Changed
- Changed how references was created

### Fixed
- Fixed reference title

### Removed
- N/A