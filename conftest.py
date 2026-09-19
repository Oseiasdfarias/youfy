"""Fixtures compartilhadas por todos os pacotes (precisam viver na raiz).

A suite roda num banco proprio, derivado da URL configurada com o sufixo
`_test`. Sem essa separacao, o `drop_all` do teardown apagaria as tabelas do
banco de desenvolvimento e deixaria a `alembic_version` carimbada para tras,
fazendo o `alembic upgrade head` seguinte virar no-op sobre um schema que nao
existe mais.

A fixture de banco nao e autouse de proposito: testes de `audio`, `spec` e
`split` sao puros e continuam rodando sem Postgres nenhum.
"""

import os
from urllib.parse import urlparse, urlunparse

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from youfy_catalog.models import Base
from youfy_catalog.settings import Settings


def _url_de_teste(base_url: str) -> str:
    partes = urlparse(base_url)
    return urlunparse(partes._replace(path=partes.path.rstrip("/") + "_test"))


def _url_administrativa(base_url: str) -> str:
    return base_url.rsplit("/", 1)[0] + "/postgres"


@pytest.fixture(scope="session")
def test_database_url() -> str:
    base_url = os.environ.get("YOUFY_DATABASE_URL") or Settings().database_url
    url = _url_de_teste(base_url)
    nome = urlparse(url).path.lstrip("/")

    admin = create_engine(_url_administrativa(base_url), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        existe = conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :nome"), {"nome": nome}
        ).scalar()
        if not existe:
            conn.execute(text(f'CREATE DATABASE "{nome}"'))
    admin.dispose()

    # Garante que qualquer codigo sob teste que leia Settings() aponte para ca.
    os.environ["YOUFY_DATABASE_URL"] = url
    from youfy_catalog.db import get_engine

    get_engine.cache_clear()
    return url


@pytest.fixture
def engine(test_database_url):
    eng = create_engine(test_database_url, future=True)
    Base.metadata.drop_all(eng)
    Base.metadata.create_all(eng)
    yield eng
    Base.metadata.drop_all(eng)
    eng.dispose()


@pytest.fixture
def session(engine):
    with sessionmaker(bind=engine, future=True)() as s:
        yield s
