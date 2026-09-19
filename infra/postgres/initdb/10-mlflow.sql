-- infra/postgres/initdb/10-mlflow.sql
SELECT 'CREATE DATABASE mlflow' WHERE NOT EXISTS (
    SELECT FROM pg_database WHERE datname = 'mlflow'
)\gexec

