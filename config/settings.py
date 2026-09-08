import os
from dotenv import load_dotenv

load_dotenv()


def _cast_int(value, default=None):
    """Cast an env-var string to int; return default for None/empty/invalid."""
    if value is None or value == "":
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def _cast_float(value, default=None):
    """Cast an env-var string to float; return default for None/empty/invalid."""
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


# LLM Configuration
FLASH_API_KEY = os.getenv("FLASH_API_KEY")
FLASH_BASE_URL = os.getenv("FLASH_BASE_URL", None)
FLASH_MODEL = os.getenv("FLASH_MODEL")

EVALUATION_API_KEY = os.getenv("EVALUATION_API_KEY")
EVALUATION_BASE_URL = os.getenv("EVALUATION_BASE_URL", None)
EVALUATION_MODEL = os.getenv("EVALUATION_MODEL")

# LiteLLM Configuration
LITELLM_DEFAULT_MODEL = os.getenv("LITELLM_DEFAULT_MODEL", "gpt-3.5-turbo")
LITELLM_DEFAULT_BASE_URL = os.getenv("LITELLM_DEFAULT_BASE_URL", None)
# Cast numeric params so litellm receives typed values (or None), never raw strings.
LITELLM_MAX_TOKENS = _cast_int(os.getenv("LITELLM_MAX_TOKENS"))
LITELLM_TEMPERATURE = _cast_float(os.getenv("LITELLM_TEMPERATURE"))
LITELLM_TOP_P = _cast_float(os.getenv("LITELLM_TOP_P"))
LITELLM_TOP_K = _cast_int(os.getenv("LITELLM_TOP_K"))

# Specific model names for strategic use (can be same as LITELLM_DEFAULT_MODEL if only one is used)
LLM_PRIMARY_MODEL = os.getenv("LLM_PRIMARY_MODEL", LITELLM_DEFAULT_MODEL)
LLM_SECONDARY_MODEL = os.getenv("LLM_SECONDARY_MODEL", FLASH_MODEL if FLASH_MODEL else LLM_PRIMARY_MODEL)

# Evolutionary Algorithm Settings
POPULATION_SIZE = int(os.getenv("POPULATION_SIZE", "5"))
GENERATIONS = int(os.getenv("GENERATIONS", "2"))
# Threshold for switching to bug-fix prompt
# If a program has errors and its correctness score is below this, a bug-fix prompt will be used.
BUG_FIX_CORRECTNESS_THRESHOLD = float(os.getenv("BUG_FIX_CORRECTNESS_THRESHOLD", "0.1"))
# Threshold for using the primary (potentially more powerful/expensive) LLM for mutation
HIGH_FITNESS_THRESHOLD_FOR_PRIMARY_LLM = float(os.getenv("HIGH_FITNESS_THRESHOLD_FOR_PRIMARY_LLM", "0.8"))
ELITISM_COUNT = 1
MUTATION_RATE = 0.7
CROSSOVER_RATE = 0.2

# Corpus Seeding Settings
SEED_FROM_CORPUS = os.getenv("SEED_FROM_CORPUS", "True").lower() == "true"
SEED_CORPUS_COUNT = int(os.getenv("SEED_CORPUS_COUNT", "2"))
BEST_CORPUS_DIR = os.getenv("BEST_CORPUS_DIR", "data/best_corpus")

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
        return FLASH_MODEL if FLASH_MODEL else LITELLM_DEFAULT_MODEL # Return default if FLASH_MODEL is not set
    return LITELLM_DEFAULT_MODEL
