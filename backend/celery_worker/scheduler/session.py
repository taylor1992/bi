# coding=utf-8
"""SQLAlchemy session."""

from contextlib import contextmanager

from kombu.utils.compat import register_after_fork
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

ModelBase = declarative_base()


@contextmanager
def session_cleanup(session):
    try:
        yield
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _after_fork_cleanup_session(session):
    session._after_fork()


class SessionManager(object):
    """Manage SQLAlchemy sessions."""

    def __init__(self):
        self._engines = {}
        self._sessions = {}
        self.forked = False
        self.prepared = False
        if register_after_fork is not None:
            register_after_fork(self, _after_fork_cleanup_session)

    def _after_fork(self):
        self.forked = True

    def get_engine(self, dburi, **kwargs):
        if self.forked:
            try:
                return self._engines[dburi]
            except KeyError:
                engine = self._engines[dburi] = create_engine(dburi, **kwargs)
                return engine
        else:
            return create_engine(dburi, poolclass=NullPool)

    def create_session(self, dburi, short_lived_sessions=False, **kwargs):
        engine = self.get_engine(dburi, **kwargs)
        if self.forked:
            if short_lived_sessions or dburi not in self._sessions:
                self._sessions[dburi] = sessionmaker(bind=engine)
            return engine, self._sessions[dburi]
        else:
            return engine, sessionmaker(bind=engine)

    def prepare_models(self, engine):
        if not self.prepared:
            ModelBase.metadata.create_all(engine)
            self.prepared = True

    def session_factory(self, dburi, **kwargs):
        engine, session = self.create_session(dburi, **kwargs)
        self.prepare_models(engine)
        return session()
