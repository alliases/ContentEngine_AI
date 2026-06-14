import taskiq_fastapi
from taskiq_redis import ListQueueBroker, RedisAsyncResultBackend

from api.config import settings

# Construct Redis URL from our configuration
REDIS_URL = f"redis://{settings.POSTGRES_HOST}:{settings.REDIS_PORT}/0"

# Initialize Result Backend and Broker
result_backend = RedisAsyncResultBackend(REDIS_URL)
broker = ListQueueBroker(REDIS_URL).with_result_backend(result_backend)

# Initialize FastAPI integration to share dependencies (like DB sessions)
taskiq_fastapi.init(broker, "api.main:app")
