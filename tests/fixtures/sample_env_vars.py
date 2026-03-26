"""Sample Python file using environment variables for testing EnvVarExtractor."""
import os

DATABASE_URL = os.environ["DATABASE_URL"]
SECRET_KEY = os.environ.get("SECRET_KEY")
DEBUG = os.environ.get("DEBUG", "False")
API_KEY = os.getenv("API_KEY")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
SMTP_PASSWORD = os.environ["SMTP_PASSWORD"]
PORT = int(os.environ.get("PORT", "8000"))
MAX_CONNECTIONS = int(os.environ.get("MAX_CONNECTIONS", "10"))
ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "localhost").split(",")

# Edge cases
_MISSING_KEY = os.environ.get("MISSING_KEY", None)
_NO_DEFAULT = os.environ.get("NO_DEFAULT")
_STRICT_KEY = os.environ["STRICT_MODE"]
