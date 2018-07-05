from enum import Enum
from redis_sessions.session import SessionStoreAlt
from redis_sessions.session import SessionStore


class States(Enum):
    NO_MIGRATION = "NO_MIGRATION"
    MIGRATING = "MIGRATING"


class SessionStoreHandler:

    def __init__(self):
        pass

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
        SessionStoreHandler.current_store, SessionStoreHandler.alternative_store = \
            SessionStoreHandler.alternative_store, SessionStoreHandler.current_store

        # Set current_state to NO_MIGRATION
        SessionStoreHandler.record_current_state(States.NO_MIGRATION)

    @staticmethod
    def record_current_state(state):
        SessionStoreHandler.current_state = state


class StoreSelector(SessionStoreHandler):

    def __init__(self, session_key, migration_mode):
        SessionStoreHandler.__init__(self)
        self.session_key = session_key
        self.migration_mode = migration_mode

    # this is the entrypoint to be called from USSD
    def get_session_store(self):
        """
        We don't know whether request session is new or already
        exists in current store or alternative store . We have to find out
        """
        session_store = self.get_current_store()
        session_exists = self.check_session_existence(session_store,
                                                      self.session_key)
        if session_exists:
            # return the current session store
            return session_store
        elif (not session_exists) and self.migration_mode:
            self.record_current_state(States.MIGRATING)
            # get and return the alternative session store
            session_store = self.get_alternative_store()
            return session_store

        elif (not self.migration_mode)\
                and (self.current_state == States.MIGRATING):

            # complete the migration by updating the current_state variable
            self.complete_migration()
            # get and return the current session store
            session_store = self.get_current_store()
            return session_store

        else:
            # return the current session store
            return session_store
