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

# Treinamento do classificador com tracking no MLflow
youfy pipeline train --epochs 10 --batch-size 32 --seed 42

# Avaliação do modelo e gate de promoção
youfy pipeline evaluate --version 1 --margin 0.005 --floor 0.40
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
        Greedy --> SplitsStore[("Partições JSON:<br/>train.json (80%)<br/>val.json (10%)<br/>test.json (10%)")]
    end

    subgraph S4["4. Estágio: train"]
        SplitsStore --> CLI4["youfy pipeline train"]
        NpyStore --> CLI4
        CLI4 --> MLTrain["youfy_ml (treino determinístico)"]
        MLTrain --> MLflowRun[("MLflow Tracking: Runs / Métricas")]
        MLTrain --> MLRegistry[("MLflow Model Registry")]
    end

    subgraph S5["5. Estágio: evaluate"]
        MLRegistry --> CLI5["youfy pipeline evaluate"]
        CLI5 --> Gate["youfy_ml.promotion (Gate de Promoção)"]
        Gate -->|Supera por margem >= 0.005| Promoted["Alias 'production'"]
    end

    classDef stage stroke:#3b82f6,stroke-width:2px;
    classDef storage stroke:#10b981,stroke-width:2px;
    classDef cli stroke:#8b5cf6,stroke-width:2px;
    class S1,S2,S3,S4,S5 stage;
    class DB,Quarantine,NpyStore,DBFeat,SplitsStore,MLflowRun,MLRegistry storage;
    class CLI1,CLI2,CLI3,CLI4,CLI5 cli;
```
