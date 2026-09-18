# Contratos Duradouros

Os contratos do Youfy são estruturas de dados e assinaturas desenhadas para resistir a toda a evolução das próximas fases do projeto.

---

## 1. FeatureSpec e Prevenção de Training/Serving Skew

A configuração de featurização viaja incorporada ao artefato do modelo treinado. O servidor de predição (`serving`) valida o `FeatureSpec` do modelo contra o featurizer em tempo de execução:

```python
@dataclass(frozen=True, slots=True)
class FeatureSpec:
    sample_rate: int = 22050
    n_fft: int = 2048
    hop_length: int = 512
    n_mels: int = 128
    n_frames: int = 1292
    fmin: float = 0.0
    fmax: float | None = None
    top_db: float = 80.0

    @property
    def effective_fmax(self) -> float:
        return self.fmax if self.fmax is not None else self.sample_rate / 2

    def fingerprint(self) -> str:
        payload = json.dumps(asdict(self), sort_keys=True).encode()
        return hashlib.sha256(payload).hexdigest()[:16]
```

### Invalidação Segura por Fingerprint
A chave SHA-256 de 16 caracteres hexadecimais gerada por `.fingerprint()` define o subdiretório de armazenamento das features:

```
data/features/melspec/<fingerprint>/
data/splits/<fingerprint>/
```

Se a taxa de amostragem (`sample_rate`), a quantidade de filtros mel (`n_mels`) ou o `hop_length` mudarem, **nenhum arquivo anterior é deletado ou corrompido**: um novo diretório é criado paralelamente, mantendo o histórico de dados 100% íntegro.

---

## 2. Schema de Eventos de Interação

Tabela append-only para registro de telemetria musical emitida tanto pelo player local quanto por sessões simuladas:

```sql
CREATE TABLE events (
  event_id           UUID PRIMARY KEY,          -- UUID gerado no cliente
  session_id         UUID NOT NULL,
  actor_id           TEXT NOT NULL,             -- 'human:osfarias' ou 'sim:u00412'
  actor_kind         VARCHAR(16) NOT NULL,      -- 'human' ou 'simulated'
  track_id           TEXT NOT NULL REFERENCES tracks(id),
  event_type         VARCHAR(24) NOT NULL,      -- play_start, pause, resume, seek, skip, complete
  ts                 TIMESTAMPTZ NOT NULL,      -- relógio do cliente
  ingested_at        TIMESTAMPTZ NOT NULL,      -- relógio do servidor
  position_ms        INTEGER NOT NULL,
  track_duration_ms  INTEGER NOT NULL,
  client_event_seq   INTEGER NOT NULL,          -- sequência ordinal na sessão
  context            JSONB NOT NULL             -- {"surface": "search", "rank": 1, "model_version": "v1"}
);
```

### Princípios do Schema
1. **`actor_id` + `actor_kind`:** Permite que populações simuladas e escutas humanas compartilhem o mesmo pipeline de eventos sem contaminação do holdout de validação.
2. **Separação de `ts` (cliente) e `ingested_at` (servidor):** Essencial para suportar buffering e reprodução offline sem distorcer janelas temporais de análise de churn ou retenção.
3. **`context.model_version`:** Toda predição ou recomendação registra qual versão do modelo motivou a reprodução, viabilizando avaliação *off-policy* e correção de viés de exposição.
4. **Sem interpretação prévia:** Não há campo booleano `liked`. Eventos guardam o fato atômico (`skip` aos 3s vs. `skip` aos 28s); interpretações analíticas são derivadas em tempo de consulta.

---

## 3. Superfície da API HTTP

| Método | Rota | Descrição |
|---|---|---|
| `GET` | `/tracks?q=&genre=&limit=` | Busca e listagem no acervo |
| `GET` | `/tracks/{id}` | Metadados da faixa e gênero |
| `GET` | `/tracks/{id}/stream` | Streaming de áudio (suporte a HTTP Range Requests) |
| `POST` | `/events` | Ingestão em lote idempotente (`ON CONFLICT DO NOTHING`) |
| `GET` | `/tracks/{id}/genre` | Predição com `model_version` ativa (503 se sem modelo promovido) |
| `GET` | `/health` | Status dos serviços e versão de modelo em `Production` |

