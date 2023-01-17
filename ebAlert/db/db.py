from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from ebAlert import create_logger
from ebAlert.core.configs import configs


log = create_logger(__name__)

engine = create_engine(f'sqlite:///{configs.FILE_LOCATION}', echo=False)

Base = declarative_base()

Session = sessionmaker(bind=engine)
