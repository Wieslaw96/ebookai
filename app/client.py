import os

from dotenv import load_dotenv
from google import genai

load_dotenv()

# MODEL_PRO wymaga planu płatnego. Na darmowym free-tier oba modele
# kierują do Flash, który jest dostępny bez limitu dziennego.
# Zmień MODEL_PRO na "gemini-2.5-pro" po włączeniu billing w Google AI Studio.
MODEL_PRO = "gemini-2.5-flash"
MODEL_FLASH = "gemini-2.5-flash"

_client: genai.Client | None = None


def get_client() -> genai.Client:
    """Return the shared Gemini client, initialising it on first call.

    Lazy init means the module can be imported safely without a key present
    (e.g. during unit tests that mock the client). The ValueError is raised
    only when an actual API call is attempted.
    """
    global _client
    if _client is None:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError(
                "GEMINI_API_KEY is not set. "
                "Copy .env.example to .env and fill in your key."
            )
        _client = genai.Client(api_key=api_key)
    return _client
