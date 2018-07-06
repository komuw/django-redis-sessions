from redis_sessions.session import SessionStoreAlt
from redis_sessions.session import SessionStore


class SessionStoreHandler:

    def __init__(self):
        pass

    @staticmethod
    def get_current_store():
        # the default session store
        return SessionStore

    @staticmethod
    def get_alternative_store():
        # the alternative session store to migrate new sessions to
        return SessionStoreAlt

    @staticmethod
    def check_session_existence(session_store, session_key):
        return session_store().exists(session_key)


class StoreSelector(SessionStoreHandler):

    def __init__(self, session_key, migration_mode, drop_original_store=False):
        SessionStoreHandler.__init__(self)

        # customer session key
        self.session_key = session_key

        # whether to migrate new sessions to the alternative store
        self.migration_mode = migration_mode

        # whether to continue checking for active sessions on the previous
        # session store after migrating new sessions to alternative store
        self.drop_original_store = drop_original_store

    def get(self):

        if not self.drop_original_store:
            session_store = self.get_current_store()
            if not self.migration_mode:
                return session_store
            else:
                session_exists = self.check_session_existence(session_store,
                                                              self.session_key)
                if session_exists:
                    # return the current session store
                    return session_store
                else:
                    return self.get_alternative_store()
        else:
            return self.get_alternative_store()
