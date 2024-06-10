from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from .models import Base

class Database:
    def __init__(self, db_name, db_user, db_password, db_host):
        self.engine = create_engine(f'mysql+mysqlconnector://{db_user}:{db_password}@{db_host}/{db_name}')
        self.session_factory = sessionmaker(bind=self.engine)
        self.Session = scoped_session(self.session_factory)
        Base.metadata.create_all(self.engine)

    def close(self):
        self.Session.remove()
        self.engine.dispose()