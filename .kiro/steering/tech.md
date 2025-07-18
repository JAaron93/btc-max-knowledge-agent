# Technology Stack

## Primary Language
- **Python** - Main development language

## Key Dependencies & Frameworks
- **Pinecone** - Vector database for knowledge retrieval
- **AI/ML Libraries** - For natural language processing and embeddings

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
- Vector embeddings for Bitcoin/blockchain knowledge
- Support for various ML model formats (.pkl, .joblib, .h5, .pth, .pt, .safetensors)
- FAISS indexing support for local vector operations