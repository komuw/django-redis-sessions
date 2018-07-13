from django.test import TestCase
from redis_sessions.session import SessionStore
import redis
import mock


class SessionMigrationTest(TestCase):
    def setUp(self):
        pass

    @mock.patch("redis_sessions.session.default_settings.SESSION_STORE_MIGRATION_MODE", 1)
    def test_new_session_with_migration_on(self):
        session_key = "hj56fgfgglk7765h"
        # trigger USSD request to generate a session
        store = SessionStore(session_key)
        store._session.keys()
        store._session_key = session_key
        store.save()
        assert store.exists(session_key)

        # session should not exist in the original store
        redis_store = redis.StrictRedis(host='redis')
        assert redis_store.get('session:'+session_key) is None

        # confirm that new sessions are being stored on the alternative store.
        redis_store = redis.StrictRedis(host='alt_redis')
        assert redis_store.get('session:'+session_key) is not None

    @mock.patch("redis_sessions.session.default_settings.SESSION_STORE_MIGRATION_MODE", 0)
    def test_session_with_migration_off(self):

        session_key = "uhjjg6675fffgs2344"
        # trigger USSD request to generate a session
        store = SessionStore(session_key)
        store._session.keys()
        store._session_key = session_key
        store.save()
        assert store.exists(session_key)

        # confirm that new sessions are being stored on the alternative store.
        redis_store = redis.StrictRedis(host='redis')
        assert redis_store.get('session:'+session_key) is not None

        # session should not exist in the alternative store.
        redis_store = redis.StrictRedis(host='alt_redis')
        assert redis_store.get('session:'+session_key) is None

    def test_old_session_with_migration_on(self):

        session_key = "uhjjg6675fffgs2322"
        # trigger USSD request to generate a session
        store = SessionStore(session_key)
        store._session.keys()
        store._session_key = session_key
        store.save()
        assert store.exists(session_key)

        with mock.patch("redis_sessions.session.default_settings.SESSION_STORE_MIGRATION_MODE", 1):
            print("testing here2")
            store = SessionStore(session_key)
            store._session.keys()
            store._session_key = session_key
            assert store.exists(session_key)
            print("end testing here")


    def test_old_session_with_full_migration_on(self):

        session_key = "uhjjg6675fffgs23288"
        # trigger USSD request to generate a session
        store = SessionStore(session_key)
        store._session.keys()
        store._session_key = session_key
        store.save()
        assert store.exists(session_key)

        with mock.patch("redis_sessions.session.default_settings.SESSION_STORE_MIGRATION_MODE", 1), \
             mock.patch("redis_sessions.session.default_settings.DROP_ORIGINAL_SESSION_STORE", 1):
            print("testing here2")
            store = SessionStore(session_key)
            store._session.keys()
            store._session_key = session_key
            assert store.exists(session_key) is not True
            print("end testing here")