import os
import redis
import time

REDIS_HOST = os.environ.get('REDIS_HOST', 'redis-db')
REDIS_PORT = int(os.environ.get('REDIS_PORT', 6379))

def get_redis_connection(max_retries=5, delay=2):
    for attempt in range(max_retries):
        try:
            return redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)
        except redis.exceptions.ConnectionError:
            if attempt < max_retries - 1:
                time.sleep(delay)
            else:
                raise

rd = get_redis_connection()

