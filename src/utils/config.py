import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    # Pinecone settings
    PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
    PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "btc-knowledge-base")

    # Embedding settings
    EMBEDDING_DIMENSION = int(os.getenv("EMBEDDING_DIMENSION", "768"))

    # Chunk settings
    CHUNK_SIZE = 1000
    CHUNK_OVERLAP = 200
    
    # URL validation settings
    ALLOW_LOCALHOST_URLS = os.getenv("ALLOW_LOCALHOST_URLS", "True").lower() == "true"

    @classmethod
    def validate(cls):
        """Validate required environment variables"""
        required_vars = ["PINECONE_API_KEY"]

        missing_vars = []
        for var in required_vars:
            if not getattr(cls, var):
                missing_vars.append(var)

        if missing_vars:
            raise ValueError(
                f"Missing required environment variables: {', '.join(missing_vars)}"
            )

        return True
