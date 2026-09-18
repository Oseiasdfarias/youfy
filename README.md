# Youfy

Laboratório de IA aplicada no formato de um player de música, sobre catálogo
com licenciamento aberto (Free Music Archive).

**Plano atual:** 1A — Fundação de Dados.
Ver `docs/superpowers/specs/` e `docs/superpowers/plans/`.

## Começando

```bash
make setup      # instala dependências
make up         # sobe o Postgres local
make test       # roda a suíte
make e2e        # pipeline ponta a ponta no micro-dump
```

## Pipeline

```bash
youfy pipeline ingest --dump-dir ./data/raw/fma
youfy pipeline featurize
youfy pipeline split --seed 42
```
