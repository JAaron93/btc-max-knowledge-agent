import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    # Pinecone settings
    PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
    PINECONE_INDEX_NAME = os.getenv(
        "PINECONE_INDEX_NAME", "btc-knowledge-base"
    )

    # Embedding settings
    EMBEDDING_DIMENSION = int(os.getenv("EMBEDDING_DIMENSION", "768"))

    # Chunk settings
    CHUNK_SIZE = 1000
    CHUNK_OVERLAP = 200

    # URL validation settings
    ALLOW_LOCALHOST_URLS = (
        os.getenv("ALLOW_LOCALHOST_URLS", "True").lower() == "true"
    )

    # Hyperbolic (GPT-OSS 120B) settings
    HYPERBOLIC_API_KEY = os.getenv("HYPERBOLIC_API_KEY")
    HYPERBOLIC_MODEL = os.getenv(
        "HYPERBOLIC_MODEL", "gpt-oss-120b"
    )
    HYPERBOLIC_API_BASE = os.getenv("HYPERBOLIC_API_BASE", "")

    # Backend selection: "pinecone" or "hyperbolic"
    _bp = os.getenv("BACKEND_PROVIDER", "pinecone")
    BACKEND_PROVIDER = _bp.strip().lower()
    USE_HYPERBOLIC = (
        os.getenv("USE_HYPERBOLIC", "false").strip().lower() == "true"
        or BACKEND_PROVIDER == "hyperbolic"
    )

    @classmethod
    def validate(cls):
        """Validate required environment variables"""
        required_vars = [
            "HYPERBOLIC_API_KEY" if cls.USE_HYPERBOLIC else "PINECONE_API_KEY"
        ]

        missing_vars = []
        for var in required_vars:
            if not getattr(cls, var):
                missing_vars.append(var)

        if missing_vars:
            missing = ", ".join(missing_vars)
            raise ValueError(
                "Missing required environment variables: " + missing
            )

        return True
