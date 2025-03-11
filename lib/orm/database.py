from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
import os
from .models import Base
from dotenv import load_dotenv
from contextlib import contextmanager

class Database:
    def __init__(self):
        # Load environment variables from .env file
        load_dotenv()

        db_name = os.getenv('db_name')
        db_user = os.getenv('db_user')
        db_password = os.getenv('db_password')
        db_host = os.getenv('db_host')

        # Change from utf8mb4 to utf8 to avoid encoding issues
        self.engine = create_engine(f'mysql+mysqlconnector://{db_user}:{db_password}@{db_host}/{db_name}?charset=utf8&collation=utf8_unicode_ci')
        self.session_factory = sessionmaker(bind=self.engine)
        self.Session = scoped_session(self.session_factory)
        self._singleton_session = None

    def get_session(self, singleton=True):
        if singleton:
            if self._singleton_session is None:
                self._singleton_session = self.Session()
            return self._singleton_session
        else:
            return self.Session()

    @contextmanager
    def session_scope(self):
        """Provide a transactional scope around a series of operations."""
        session = self.get_session()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def get_engine(self):
        return self.engine
    
    def close(self):
        if self._singleton_session is not None:
            self._singleton_session.close()
        self.Session.remove()
        self.engine.dispose()

# Example usage
db_instance = Database()