from pathlib import Path

APP_ID = 5692993
APP_SLUG = "aps-tis-readonly"
ORG = "APS-TIS"
REPO = "APS-TIS"
FULL_REPO = "APS-TIS/APS-TIS"
API_BASE = "https://api.github.com"
API_VERSION = "2022-11-28"
KEY_PATH = Path(r"C:\APS-TIS-MCP\credentials\aps-tis-readonly.pem")
EXPECTED_PERMISSIONS = {"contents": "read", "issues": "read", "metadata": "read"}
MAX_RESPONSE_BYTES = 8 * 1024 * 1024
MAX_FILE_BYTES = 512 * 1024
MAX_LIST_ITEMS = 500
MAX_SEARCH_FILES = 25
MAX_SEARCH_RESULTS = 20
