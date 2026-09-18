# conftest.py  (raiz do repositorio: estas fixtures precisam valer para todos os pacotes)
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from youfy_catalog.models import Base
from youfy_catalog.settings import Settings


@pytest.fixture
def engine():
    eng = create_engine(Settings().database_url, future=True)
    Base.metadata.drop_all(eng)
    Base.metadata.create_all(eng)
    yield eng
    Base.metadata.drop_all(eng)

@pytest.fixture
def session(engine):
    with sessionmaker(bind=engine, future=True)() as s:
        yield s
