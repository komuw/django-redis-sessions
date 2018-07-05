from settings import *

# this is the alternative redis store instance configs
SESSION_REDIS = getattr(settings, 'ALT_SESSION_REDIS', {})

SESSION_REDIS_HOST = SESSION_REDIS.get('host', 'localhost')
SESSION_REDIS_PORT = SESSION_REDIS.get('port', 6379)
SESSION_REDIS_SOCKET_TIMEOUT = SESSION_REDIS.get('socket_timeout', 0.1)
SESSION_REDIS_RETRY_ON_TIMEOUT = SESSION_REDIS.get('retry_on_timeout', False)
SESSION_REDIS_DB = SESSION_REDIS.get('db', 0)
SESSION_REDIS_PREFIX = SESSION_REDIS.get('prefix', '')
SESSION_REDIS_PASSWORD = SESSION_REDIS.get('password', None)
SESSION_REDIS_UNIX_DOMAIN_SOCKET_PATH = SESSION_REDIS.get('unix_domain_socket_path', None)
SESSION_REDIS_URL = SESSION_REDIS.get('url', None)
