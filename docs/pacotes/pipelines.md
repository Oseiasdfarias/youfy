# Pacote `youfy-pipelines`

O pacote `pipelines` é a camada de orquestração do Youfy. É o **único componente autorizado a compor `youfy-audio` e `youfy-catalog`**.

---

## CLI Canônica (`youfy`)

Construída com **Typer**, a interface de linha de comando é o ponto de entrada oficial para todas as operações offline do Youfy:

```bash
# Ajuda geral dos estágios
youfy pipeline --help

# Ingestão do acervo
youfy pipeline ingest --dump-dir ./data/raw/fma --subset small

# Extração de mel-espectrogramas
youfy pipeline featurize --n-mels 128 --hop-length 512

# Particionamento estratificado agrupado por artista
youfy pipeline split --seed 42
```

---

## Logging Estruturado em JSON (`structlog`)

Seguindo as melhores práticas para observabilidade e rastreabilidade:
- Eventos e métricas emitidos em JSON estruturado com timestamps ISO em UTC.
- Compatível com coletores modernos de logs (FluentBit, Vector, Datadog).

Exemplo de log emitido:

```json
{
  "event": "ingest.concluido",
  "level": "info",
  "timestamp": "2026-09-18T22:30:00.000000Z",
  "total": 8000,
  "ingeridas": 7994,
  "falhas": 6,
  "taxa_de_falha": 0.0008
}
```

---

## Fluxo de Orquestração dos Pipelines Offline

O pacote `youfy-pipelines` coordena os 3 estágios determinísticos, conectando o catálogo relacional ao armazenamento de matrizes e partições de ML:

```mermaid
flowchart TD
    subgraph S1["1. Estágio: ingest"]
        FMA["Dump FMA (CSV + MP3s)"] --> CLI1["youfy pipeline ingest"]
        CLI1 --> Repo["youfy_catalog.repository"]
        Repo --> DB[("PostgreSQL: tracks / artists / genres")]
        Repo -. falhas .-> Quarantine[("ingest_failures")]
    end

    subgraph S2["2. Estágio: featurize"]
        DB --> CLI2["youfy pipeline featurize"]
        CLI2 --> Spec["FeatureSpec (fingerprint SHA-256)"]
        Spec --> AudioDSP["youfy_audio (decode + melspec)"]
        AudioDSP --> NpyStore[("Disco: data/features/{fingerprint}/{id}.npy")]
        AudioDSP --> DBFeat[("PostgreSQL: features")]
    end

    subgraph S3["3. Estágio: split"]
        DBFeat --> CLI3["youfy pipeline split"]
        CLI3 --> Greedy["Algoritmo Guloso por Artista<br/>(seed determinística)"]
        Greedy --> Parquet[("Partições Parquet:<br/>train.parquet (80%)<br/>val.parquet (10%)<br/>test.parquet (10%)")]
    end

    classDef stage fill:#18181b,stroke:#3b82f6,stroke-width:1.5px,color:#f4f4f5;
    classDef storage fill:#09090b,stroke:#10b981,stroke-width:1.5px,color:#34d399;
    classDef cli fill:#27272a,stroke:#a855f7,stroke-width:1.5px,color:#e4e4e7;
    class S1,S2,S3 stage;
    class DB,Quarantine,NpyStore,DBFeat,Parquet storage;
    class CLI1,CLI2,CLI3 cli;
```
