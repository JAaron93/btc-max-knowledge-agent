# Project Structure

## Root Directory Organization
```
btc-max-knowledge-agent/
├── .git/                 # Git version control
├── .kiro/               # Kiro AI assistant configuration
│   └── steering/        # AI guidance documents
├── .gitignore           # Git ignore patterns
├── LICENSE              # MIT License
└── README.md            # Project documentation
```

## Expected Structure (as project develops)
```
btc-max-knowledge-agent/
├── src/                 # Source code
│   ├── agents/          # Knowledge agent implementations
│   ├── retrieval/       # Pinecone and vector operations
│   ├── knowledge/       # Bitcoin/blockchain knowledge processing
│   └── utils/           # Utility functions
├── data/                # Training data and knowledge base (gitignored)
├── models/              # ML models and embeddings (gitignored)
├── config/              # Configuration files
├── tests/               # Unit and integration tests
├── requirements.txt     # Python dependencies
└── .env.example         # Environment variable template
```

## File Naming Conventions
- Use snake_case for Python files and directories
- Use descriptive names that reflect functionality
- Separate concerns into logical modules

## Key Directories (when created)
- **src/**: All source code
- **data/**: Knowledge base and training data (excluded from git)
- **models/**: Trained models and embeddings (excluded from git)
- **config/**: Configuration and settings
- **tests/**: Test files following pytest conventions

## Environment Files
- `.env`: Local environment variables (gitignored)
- `.env.example`: Template for required environment variables
- Store API keys, database URLs, and sensitive configuration in environment variables