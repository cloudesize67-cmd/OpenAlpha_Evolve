import os
from dotenv import load_dotenv

load_dotenv()

# -----------------------------------------------------------------------------
# Multi-provider LLM Configuration
# -----------------------------------------------------------------------------
# OpenAlpha_Evolve uses three strategic model roles for the recursive learning
# loop. Each role can point to a different provider/model via LiteLLM strings.
# Set the model name, optional base_url, and optional api_key override below.
# If a role's API_KEY is omitted, LiteLLM falls back to its provider-standard
# env var (e.g. ANTHROPIC_API_KEY, MOONSHOT_API_KEY, GEMINI_API_KEY).
# -----------------------------------------------------------------------------

# --- Claude Sonnet 5 (Anthropic) ---
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "anthropic/claude-sonnet-5")
CLAUDE_BASE_URL = os.getenv("CLAUDE_BASE_URL", None)
CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY", os.getenv("ANTHROPIC_API_KEY"))

# --- Kimi K3 (Moonshot AI) ---
KIMI_MODEL = os.getenv("KIMI_MODEL", "moonshot/kimi-k3")
KIMI_BASE_URL = os.getenv("KIMI_BASE_URL", None)
KIMI_API_KEY = os.getenv("KIMI_API_KEY", os.getenv("MOONSHOT_API_KEY"))

# --- Gemini 3.1 Pro (Google) ---
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini/gemini-3.1-pro-preview")
GEMINI_BASE_URL = os.getenv("GEMINI_BASE_URL", None)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", os.getenv("GOOGLE_API_KEY"))

# Legacy flash/pro model variables kept for backward compatibility
FLASH_API_KEY = os.getenv("FLASH_API_KEY")
FLASH_BASE_URL = os.getenv("FLASH_BASE_URL", None)
FLASH_MODEL = os.getenv("FLASH_MODEL")

EVALUATION_API_KEY = os.getenv("EVALUATION_API_KEY")
EVALUATION_BASE_URL = os.getenv("EVALUATION_BASE_URL", None)
EVALUATION_MODEL = os.getenv("EVALUATION_MODEL")

# LiteLLM Configuration
LITELLM_DEFAULT_MODEL = os.getenv("LITELLM_DEFAULT_MODEL", "gpt-3.5-turbo")
LITELLM_DEFAULT_BASE_URL = os.getenv("LITELLM_DEFAULT_BASE_URL", None)
LITELLM_MAX_TOKENS = os.getenv("LITELLM_MAX_TOKENS")
LITELLM_TEMPERATURE = os.getenv("LITELLM_TEMPERATURE")
LITELLM_TOP_P = os.getenv("LITELLM_TOP_P")
LITELLM_TOP_K = os.getenv("LITELLM_TOP_K")

# Specific model names for strategic use (can be same as LITELLM_DEFAULT_MODEL if only one is used)
LLM_PRIMARY_MODEL = os.getenv("LLM_PRIMARY_MODEL", GEMINI_MODEL if GEMINI_MODEL else LITELLM_DEFAULT_MODEL)
LLM_SECONDARY_MODEL = os.getenv("LLM_SECONDARY_MODEL", KIMI_MODEL if KIMI_MODEL else LLM_PRIMARY_MODEL)

# Enable automatic model cycling across the three providers for mutation tasks.
# When True, the TaskManager rotates between Claude, Kimi, and Gemini each
# generation, increasing diversity and robustness of the evolutionary loop.
ENABLE_MODEL_CYCLING = os.getenv("ENABLE_MODEL_CYCLING", "True").lower() == "true"

# Evolutionary Algorithm Settings
POPULATION_SIZE = 5
GENERATIONS = 2
# Threshold for switching to bug-fix prompt
# If a program has errors and its correctness score is below this, a bug-fix prompt will be used.
BUG_FIX_CORRECTNESS_THRESHOLD = float(os.getenv("BUG_FIX_CORRECTNESS_THRESHOLD", "0.1"))
# Threshold for using the primary (potentially more powerful/expensive) LLM for mutation
HIGH_FITNESS_THRESHOLD_FOR_PRIMARY_LLM = float(os.getenv("HIGH_FITNESS_THRESHOLD_FOR_PRIMARY_LLM", "0.8"))
ELITISM_COUNT = 1
MUTATION_RATE = 0.7
CROSSOVER_RATE = 0.2

# Island Model Settings
NUM_ISLANDS = 4  # Number of subpopulations
MIGRATION_INTERVAL = 4  # Number of generations between migrations
ISLAND_POPULATION_SIZE = POPULATION_SIZE // NUM_ISLANDS  # Programs per island
MIN_ISLAND_SIZE = 2  # Minimum number of programs per island
MIGRATION_RATE = 0.2  # Rate at which programs migrate between islands

# Debug Settings
DEBUG = os.getenv("DEBUG", "False").lower() == "true"
EVALUATION_TIMEOUT_SECONDS = 800

# Docker Execution Settings
DOCKER_IMAGE_NAME = os.getenv("DOCKER_IMAGE_NAME", "code-evaluator:latest")
DOCKER_NETWORK_DISABLED = os.getenv("DOCKER_NETWORK_DISABLED", "True").lower() == "true"

DATABASE_TYPE = "json"
DATABASE_PATH = "program_database.json"

# Logging Configuration
LOG_LEVEL = "DEBUG" if DEBUG else "INFO"
LOG_FILE = "alpha_evolve.log"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

API_MAX_RETRIES = 5
API_RETRY_DELAY_SECONDS = 10

RL_TRAINING_INTERVAL_GENERATIONS = 50
RL_MODEL_PATH = "rl_finetuner_model.pth"

MONITORING_DASHBOARD_URL = "http://localhost:8080"

def get_setting(key, default=None):
    """
    Retrieves a setting value.
    For LLM models, it specifically checks if the primary choice is available,
    otherwise falls back to a secondary/default if defined.
    """
    return globals().get(key, default)

def get_llm_model(model_type="default"):
    if model_type == "default":
        return LITELLM_DEFAULT_MODEL
    elif model_type == "flash":
        return FLASH_MODEL if FLASH_MODEL else LITELLM_DEFAULT_MODEL
    elif model_type == "claude":
        return CLAUDE_MODEL if CLAUDE_MODEL else LITELLM_DEFAULT_MODEL
    elif model_type == "kimi":
        return KIMI_MODEL if KIMI_MODEL else LITELLM_DEFAULT_MODEL
    elif model_type == "gemini":
        return GEMINI_MODEL if GEMINI_MODEL else LITELLM_DEFAULT_MODEL
    # Fallback for any other model_type not explicitly handled
    return LITELLM_DEFAULT_MODEL


def get_model_extra_params(model_name: str) -> dict:
    """
    Return provider-specific extra parameters (api_key, base_url) for a given
    LiteLLM model string. This allows each role to authenticate against its
    own provider even when multiple providers are used simultaneously.
    """
    extra = {}
    model_lower = (model_name or "").lower()

    if model_lower.startswith("anthropic/") or "claude" in model_lower:
        if CLAUDE_API_KEY:
            extra["api_key"] = CLAUDE_API_KEY
        if CLAUDE_BASE_URL:
            extra["base_url"] = CLAUDE_BASE_URL
    elif model_lower.startswith("moonshot/") or "kimi" in model_lower:
        if KIMI_API_KEY:
            extra["api_key"] = KIMI_API_KEY
        if KIMI_BASE_URL:
            extra["base_url"] = KIMI_BASE_URL
    elif model_lower.startswith("gemini/") or model_lower.startswith("vertex_ai/"):
        if GEMINI_API_KEY:
            extra["api_key"] = GEMINI_API_KEY
        if GEMINI_BASE_URL:
            extra["base_url"] = GEMINI_BASE_URL

    return extra

                                 
