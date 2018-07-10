import redis

try:
    from django.utils.encoding import force_unicode
except ImportError:  # Python 3.*
    from django.utils.encoding import force_text as force_unicode
from django.contrib.sessions.backends.base import SessionBase, CreateError
from redis_sessions import settings as default_settings
from redis_sessions import alt_settings
import base64
from structlog import get_logger
logger = get_logger(__name__)


class RedisServer:
    __redis = {}

    def __init__(self, session_key, settings):
        self.session_key = session_key
        self.connection_key = ''
        self.settings = settings

        if self.settings.SESSION_REDIS_SENTINEL_LIST is not None:
            self.connection_type = 'sentinel'
        else:
            if self.settings.SESSION_REDIS_POOL is not None:
                server_key, server = self.get_server(session_key, self.settings.SESSION_REDIS_POOL)
                self.connection_key = str(server_key)
                self.settings.SESSION_REDIS_HOST = getattr(server, 'host', 'localhost')
                self.settings.SESSION_REDIS_PORT = getattr(server, 'port', 6379)
                self.settings.SESSION_REDIS_DB = getattr(server, 'db', 0)
                self.settings.SESSION_REDIS_PASSWORD = getattr(server, 'password', None)
                self.settings.SESSION_REDIS_URL = getattr(server, 'url', None)
                self.settings.SESSION_REDIS_UNIX_DOMAIN_SOCKET_PATH = getattr(server,'unix_domain_socket_path', None)

            if self.settings.SESSION_REDIS_URL is not None:
                self.connection_type = 'redis_url'
            elif self.settings.SESSION_REDIS_HOST is not None:
                self.connection_type = 'redis_host'
            elif self.settings.SESSION_REDIS_UNIX_DOMAIN_SOCKET_PATH is not None:
                self.connection_type = 'redis_unix_url'

        self.connection_key += self.connection_type

    def get_server(self, key, servers_pool):
        total_weight = sum([row.get('weight', 1) for row in servers_pool])
        pos = 0
        for i in range(3, -1, -1):
            pos = pos * 2 ** 8 + ord(key[i])
        pos = pos % total_weight

        pool = iter(servers_pool)
        server = next(pool)
        server_key = 0
        i = 0
        while i < total_weight:
            if i <= pos < (i + server.get('weight', 1)):
                return server_key, server
            i += server.get('weight', 1)
            server = next(pool)
            server_key += 1

        return

    def get(self):
        if self.connection_key in self.__redis:
            return self.__redis[self.connection_key]

        if self.connection_type == 'sentinel':
            from redis.sentinel import Sentinel
            self.__redis[self.connection_key] = Sentinel(
                self.settings.SESSION_REDIS_SENTINEL_LIST,
                socket_timeout=self.settings.SESSION_REDIS_SOCKET_TIMEOUT,
                retry_on_timeout=self.settings.SESSION_REDIS_RETRY_ON_TIMEOUT,
                db=getattr(self.settings, 'SESSION_REDIS_DB', 0),
                password=getattr(self.settings, 'SESSION_REDIS_PASSWORD', None)
            ).master_for(self.settings.SESSION_REDIS_SENTINEL_MASTER_ALIAS)

        elif self.connection_type == 'redis_url':
            self.__redis[self.connection_key] = redis.StrictRedis.from_url(
                self.settings.SESSION_REDIS_URL,
                socket_timeout=self.settings.SESSION_REDIS_SOCKET_TIMEOUT
            )
        elif self.connection_type == 'redis_host':
            self.__redis[self.connection_key] = redis.StrictRedis(
                host=self.settings.SESSION_REDIS_HOST,
                port=self.settings.SESSION_REDIS_PORT,
                socket_timeout=self.settings.SESSION_REDIS_SOCKET_TIMEOUT,
                retry_on_timeout=self.settings.SESSION_REDIS_RETRY_ON_TIMEOUT,
                db=self.settings.SESSION_REDIS_DB,
                password=self.settings.SESSION_REDIS_PASSWORD
            )
        elif self.connection_type == 'redis_unix_url':
            self.__redis[self.connection_key] = redis.StrictRedis(
                unix_socket_path=self.settings.SESSION_REDIS_UNIX_DOMAIN_SOCKET_PATH,
                socket_timeout=self.settings.SESSION_REDIS_SOCKET_TIMEOUT,
                retry_on_timeout=self.settings.SESSION_REDIS_RETRY_ON_TIMEOUT,
                db=self.settings.SESSION_REDIS_DB,
                password=self.settings.SESSION_REDIS_PASSWORD,
            )

        return self.__redis[self.connection_key]


class SessionStore(SessionBase):
    """
    Implements Redis database session store.
    """
    def __init__(self, session_key=None):
        super(SessionStore, self).__init__(session_key)
        self.conf = "default_settings"
        if self.get_conf(session_key) == 'alt_settings':
            settings = alt_settings
        else:
            settings = default_settings

        self.server = self.get_redis_server(session_key, settings)

    # overriding this to support pickle serializer.
    def __getstate__(self):
        # capture what is normally pickled.
        state = self.__dict__.copy()

        # replace the server instance.
        state['server'] = self.session_key

        return state

    # overriding this to support pickle serializer.
    def __setstate__(self, new_state):
        # recreate server instance
        if self.conf == 'alt_settings':
            settings = alt_settings
        else:
            settings = default_settings
        new_state['server'] = self.get_redis_server(new_state['server'], settings)

        # re-instate our __dict__ state from the pickled state
        self.__dict__.update(new_state)

    # overriding the default encoding to reduce the amount
    def encode(self, session_dict):
        """Returns the given session dictionary serialized and encoded as a string."""
        serialized = self.serializer().dumps(session_dict)
        hash = self._hash(serialized)
        return base64.b64encode(hash.encode() + b":" + serialized)

    @staticmethod
    def get_redis_server(session_key, conf):
        return RedisServer(session_key, conf).get()

    def load(self):
        try:
            session_data = self.server.get(
                self.get_real_stored_key(self._get_or_create_session_key())
            )
            if session_data is None:
                # force it to session key as none and return empty dict.
                raise ValueError("session key does not exists.")
            return self.decode(force_unicode(session_data))
        except:
            self._session_key = None
            return {}

    def exists(self, session_key):
        return self.server.exists(self.get_real_stored_key(session_key))

    def create(self):
        while True:
            self._session_key = self._get_new_session_key()

            try:
                self.save(must_create=True)
            except CreateError:
                # Key wasn't unique. Try again.
                continue
            self.modified = True
            return

    def save(self, must_create=False):
        if self.session_key is None:
            return self.create()
        if must_create and self.exists(self._get_or_create_session_key()):
            raise CreateError
        data = self.encode(self._get_session(no_load=must_create))
        if redis.VERSION[0] >= 2:
            self.server.setex(
                self.get_real_stored_key(self._get_or_create_session_key()),
                self.get_expiry_age(),
                data
            )
        else:
            self.server.set(
                self.get_real_stored_key(self._get_or_create_session_key()),
                data
            )
            self.server.expire(
                self.get_real_stored_key(self._get_or_create_session_key()),
                self.get_expiry_age()
            )

    def delete(self, session_key=None):
        if session_key is None:
            if self.session_key is None:
                return
            session_key = self.session_key
        try:
            self.server.delete(self.get_real_stored_key(session_key))
        except:
            pass

    @classmethod
    def clear_expired(cls):
        pass

    def get_real_stored_key(self, session_key):
        """Return the real key name in redis storage
        @return string
        """

        # supporting both None and int as session key.
        if session_key is None:
            session_key = ''
        else:
            session_key = str(session_key)

        if self.conf == 'alt_settings':
            prefix = alt_settings.SESSION_REDIS_PREFIX
        else:
            prefix = default_settings.SESSION_REDIS_PREFIX
        if not prefix:
            return session_key
        return ':'.join([prefix, session_key])

    def get_conf(self, session_key):
        session_existence_check = (not default_settings.DROP_ORIGINAL_SESSION_STORE and default_settings.SESSION_STORE_MIGRATION_MODE)
        no_session_existence_check = (default_settings.DROP_ORIGINAL_SESSION_STORE and default_settings.SESSION_STORE_MIGRATION_MODE)
        if session_existence_check:
            logger.info(SESSION_KEY=session_key)
            # check for session existence in the current store
            self.server = self.get_redis_server(session_key, default_settings)
            if self.exists(session_key):
                logger.info("using default settings 1")
                conf = "default_settings"
            else:
                logger.info("using alt settings 1")
                conf = "alt_settings"

        elif no_session_existence_check:
            logger.info("using alt settings 2")
            conf = "alt_settings"
        else:
            logger.info("using default settings 2")
            conf = "default_settings"

        return conf
