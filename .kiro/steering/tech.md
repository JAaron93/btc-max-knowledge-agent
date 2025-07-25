# Technology Stack

## Primary Language
- **Python** - Main development language

## Key Dependencies & Frameworks
- **Pinecone** - Vector database for knowledge retrieval and assistant functionality
- **FastAPI** - Modern web framework for building APIs
- **Gradio** - Web UI framework for interactive interfaces
- **ElevenLabs API** - Text-to-speech synthesis via aiohttp client
- **Pydantic** - Data validation and settings management

## Development Environment
- Python virtual environment management (supports venv, pipenv, poetry, uv, pdm, pixi)
- Environment variables for configuration (.env files)

## Common Commands
```bash
# Environment setup
python -m venv venv
source venv/bin/activate  # On macOS/Linux
pip install -r requirements.txt

# Alternative with uv (if used)
uv sync
uv run python main.py

# Alternative with poetry (if used)
poetry install
poetry run python main.py
```

## Configuration
- Environment variables stored in `.env` files
- API keys and secrets managed through environment variables
- Pinecone configuration for vector database connection

## Data Handling
- The Pinecone Assistant automatically handles vector embeddings for Bitcoin/blockchain knowledge