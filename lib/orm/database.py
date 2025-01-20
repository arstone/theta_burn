from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
import os
from .models import Base
from dotenv import load_dotenv

class Database:
    def __init__(self):

        # Load environment variables from .env file
        load_dotenv()

        db_name = os.getenv('db_name')
        db_user = os.getenv('db_user')
        db_password = os.getenv('db_password')
        db_host = os.getenv('db_host')

        self.engine = create_engine(f'mysql+mysqlconnector://{db_user}:{db_password}@{db_host}/{db_name}')
        self.session_factory = sessionmaker(bind=self.engine)
        self._session = None

    def get_session(self):
        if self._session is None:
            self.Session = scoped_session(self.session_factory)
            self._session = self.Session()
        return self._session

    def get_engine(self):
        return self.engine
    
    def close(self):
        if self._session is not None:
            self._session.close()
        if hasattr(self, 'Session'):
            self.Session.remove()
        self.engine.dispose()