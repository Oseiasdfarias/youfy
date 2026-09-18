# Pipelines Offline

O Youfy opera três estágios de dados pré-treino. Cada estágio é **idempotente**, **retomável** e pode ser executado de forma isolada.

---

## 1. Estágio `ingest`

Processa o dump do FMA, validando o cabeçalho técnico de cada clipe de áudio via `probe` e salvando o catálogo no Postgres.

```bash
youfy pipeline ingest --dump-dir ./data/raw/fma --subset small --max-failure-rate 0.02
```

### Comportamento de Quarentena
- Falhas em arquivos (mp3 corrompido, arquivo ausente) ou metadados ausentes (sem gênero) são gravados na tabela `ingest_failures`.
- O pipeline não é abortado por causa de faixas isoladas.
- **Gate de integridade:** Se a taxa global de falhas exceder `--max-failure-rate` (default 2%), o comando encerra com código de saída 1.

---

## 2. Estágio `featurize`

Extrai mel-espectrogramas de todas as faixas válidas e salva em arrays NumPy (`.npy`) otimizados para leitura durante o treino.

```bash
youfy pipeline featurize --n-mels 128 --hop-length 512 --n-frames 1292
```

### Características
- **Cache e Retomada:** Se o processo for interrompido e executado novamente, faixas já computadas são identificadas pela existência do arquivo `.npy` e ignoradas (`skipped`).
- **Isolamento por Fingerprint:** Salva em `data/features/melspec/<fingerprint>/` junto a um `_manifest.json` com os hiperparâmetros utilizados.

---

## 3. Estágio `split`

Gera partições determinísticas (`train.json`, `val.json`, `test.json`) para alimentar os DataLoaders de treino.

```bash
youfy pipeline split --seed 42
```

### Características
- **Disjunção estrita de artistas:** Nenhum artista tem faixas divididas entre conjuntos distintos.
- **Estratificação por gênero:** Mantém o equilíbrio entre classes em todos os splits.
- Salva o resultado em `data/splits/<fingerprint>/`.

---

## Ciclo de Vida Completo do Dado Offline

```mermaid
sequenceDiagram
    autonumber
    actor Dev as Engenheiro MLOps / CI
    participant CLI as youfy pipeline
    participant DB as Postgres (Catalog)
    participant Disk as Armazenamento Local
    participant DVC as DVC Remote

    Note over Dev,CLI: 1. Ingestão e Gate de Quarentena
    Dev->>CLI: youfy pipeline ingest --dump-dir ./data/raw/fma
    CLI->>Disk: probe() em cada MP3
    CLI->>DB: upsert_artist(), upsert_track()
    alt Falha de leitura / áudio quebrado
        CLI->>DB: record_failure() (tabela ingest_failures)
    end
    CLI-->>Dev: ingest.concluido (taxa_falhas < 2%)

    Note over Dev,CLI: 2. Extração Determinística de Features
    Dev->>CLI: youfy pipeline featurize --n-mels 128
    CLI->>DB: listar faixas ativas
    loop Para cada faixa pendente
        CLI->>Disk: decode() + compute_melspec()
        CLI->>Disk: salvar {id}.npy em data/features/{fingerprint}/
        CLI->>DB: registrar feature e fingerprint
    end
    CLI-->>Dev: featurize.concluido

    Note over Dev,CLI: 3. Particionamento Estratificado
    Dev->>CLI: youfy pipeline split --seed 42
    CLI->>DB: carregar catálogo completo
    CLI->>CLI: make_splits() (algoritmo guloso por artista)
    CLI->>Disk: salvar train/val/test (.parquet / .json)
    CLI-->>Dev: split.concluido (interseção = ∅)

    Note over Dev,DVC: 4. Versionamento de Artefatos
    Dev->>DVC: make dvc-push
    DVC-->>Dev: features e splits sincronizados
```

