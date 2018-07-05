from enum import Enum
from redis_sessions.session import SessionStoreAlt
from redis_sessions.session import SessionStore


class States(Enum):
    NO_MIGRATION = "NO_MIGRATION"
    MIGRATING = "MIGRATING"


class SessionStoreHandler:

    def __init__(self):
        pass

    # [migration_mode] is updated by the Admin as a functional flag
    migration_mode = False

    # below values are set and updated by the SessionStoreHandler
    # they need to be stored persistently in the db
    current_store = "session_store"
    alternative_store = "session_store_alt"
    current_state = States.NO_MIGRATION

    @staticmethod
    def get_store_object(store_key):
        if store_key == "session_store_alt":
            return SessionStoreAlt

        return SessionStore

    @staticmethod
    def get_current_store():
        store_key = SessionStoreHandler.current_store
        return SessionStoreHandler.get_store_object(store_key)

    @staticmethod
    def get_alternative_store():
        store_key = SessionStoreHandler.alternative_store
        return SessionStoreHandler.get_store_object(store_key)

    @staticmethod
    def check_session_existence(session_store, session_key):
        return session_store().exists(session_key)

    @staticmethod
    def complete_migration():
        # swap value of [current] with value of [alternative]
        SessionStoreHandler.current, SessionStoreHandler.alternative = \
            SessionStoreHandler.alternative, SessionStoreHandler.current

        # Set current_state to NO_MIGRATION
        SessionStoreHandler.record_current_state(States.NO_MIGRATION)

    @staticmethod
    def migrate_now():
        return SessionStoreHandler.migration_mode

    @staticmethod
    def record_current_state(state):
        SessionStoreHandler.current_state = state


# this is the entrypoint to be called from USSD
def get_session_store(session_key):
    """
    We don't know whether request session is new or already
    exists in current store or alternative store . We have to find out
    """
    session_store = SessionStoreHandler.get_current_store()
    session_exists = SessionStoreHandler.check_session_existence(session_store,
                                                                 session_key)
    if session_exists:
        # return the current session store
        return session_store
    elif (not session_exists) and (SessionStoreHandler.migrate_now()):
        SessionStoreHandler.record_current_state(States.MIGRATING)
        # get and return the alternative session store
        session_store = SessionStoreHandler.get_alternative_store()
        return session_store

    elif (not SessionStoreHandler.migrate_now())\
            and (SessionStoreHandler.current_state == States.MIGRATING):
        SessionStoreHandler.complete_migration()
        # get and return the current session store
        session_store = SessionStoreHandler.get_current_store()
        return session_store

    else:
        # return the current session store
        return session_store
