# Youfy — Spec 1: Loop Fechado Mínimo

**Data:** 2026-09-18
**Status:** aprovado, aguardando plano de implementação
**Subprojeto:** 1 de N (ver §11)

---

## 1. Contexto e objetivo

O Youfy é um laboratório pessoal de IA aplicada, no formato de um player de música. O produto existe para dar carga real aos modelos; os modelos e seu ciclo de vida são o objetivo.

**Critério de sucesso do projeto:** profundidade em ML e MLOps. Não amplitude de infraestrutura, não vitrine de portfólio, não produto de uso diário. Toda decisão neste documento se subordina a isso — é o que justifica um player em TUI e uma infra deliberadamente magra.

**Objetivo desta spec:** provar que o ciclo gira de ponta a ponta. Catálogo ingerido, features extraídas, modelo treinado com rastreabilidade, modelo promovido por critério, modelo servido, player tocando e emitindo eventos, eventos persistidos. Cada camada é fina de propósito — **exceto a espinha de MLOps**, que nasce com rigor porque é a parte cara de retrofitar.

---

## 2. Decisões estruturais e seu porquê

### 2.1 A fonte de catálogo não é o YouTube

A concepção original era raspar o YouTube. Foi descartada após análise das fontes primárias. Resumo do que inviabiliza:

- **Termos de Serviço do YouTube:** proíbem acesso por meios automatizados (robôs, scrapers), exceto buscadores públicos conforme robots.txt ou com permissão escrita.
- **Developer Policies, III.I.7-8:** proíbem "separate, isolate, or modify the audio or video components" — inviabiliza reprodução somente-áudio, que é a essência de um app de música.
- **III.I.9:** proíbe player em background.
- **III.I.1:** proíbe criar "substitute for, or substantially similar service to" as aplicações do YouTube. Um clone de player de música é a definição literal.
- **III.E.4:** dados da API não podem ser retidos além de 30 dias — inviabiliza dataset longitudinal.
- **Quota:** 10.000 unidades/dia, `search.list` custa 100 → 100 buscas/dia. Ampliação exige auditoria de compliance.

Premissa adicional que se mostrou falsa: estar no YouTube sem violar direitos de terceiros não concede licença de redistribuição. O uploader mantém copyright; a licença concedida cobre acesso *através do Serviço*.

**Consequência:** o catálogo vem de fontes com licenciamento aberto. Fonte primária desta spec: **Free Music Archive (FMA)**, que além de livre é benchmark acadêmico consolidado em Music Information Retrieval — o que torna as métricas comparáveis com a literatura. Jamendo e Audius entram em spec posterior como camada de streaming ao vivo.

### 2.2 O sinal de interação vem de população simulada + escuta real

Com um único usuário, o ciclo de MLOps é anêmico: sem potência estatística não há A/B, sem população não há filtragem colaborativa, sem volume não há drift observável.

**Decisão:** uma população sintética com preferências latentes gera sessões de escuta (abordagem no espírito de RecSim/RecoGym). Isso destrava loop fechado real: bandits, A/B com potência, avaliação counterfactual e drift induzível de propósito para validar o monitoramento.

A escuta humana real permanece como **holdout honesto**, nunca misturada. É o que protege contra o autoengano de validar o simulador com o próprio simulador.

O simulador **não** faz parte desta spec, mas o schema de evento já o acomoda (§7.1).

### 2.3 O primeiro modelo é um classificador de gênero supervisionado

CNN sobre mel-espectrograma, usando os rótulos hierárquicos que o FMA já traz. Escolhido por ser o caminho mais curto até "existe modelo servindo, com métrica e com retreino" — que é o que permite exercitar o ciclo cedo. Métricas limpas, comparáveis com a literatura, e a camada penúltima já serve de embedding inicial para o recomendador futuro.

Descartados para esta fatia: representação auto-supervisionada (avaliação indireta atrasa a métrica de produção), multi-label de mood (desbalanceamento complica calibração logo no primeiro modelo), qualidade técnica de áudio (pouco útil como representação de item).

### 2.4 Fatia vertical fina, não fundação horizontal

Descartado "fundação de dados primeiro": passa-se tempo demais no encanamento sem tocar música nem treinar nada, e é o modo mais comum de um projeto pessoal morrer. Descartado "modelo primeiro": produz repositório de notebooks, não sistema — e é justamente o que não ensina MLOps.

A correção aplicada à fatia vertical: **fina em tudo, exceto versionamento de dado, tracking, registry e reprodutibilidade**, que entram completos desde o primeiro commit.

---

## 3. Escopo

### 3.1 Dentro

Ingestão do `fma_small` (8.000 clipes de 30s, ~7GB, 8 gêneros balanceados) → catálogo normalizado → extração de mel-espectrogramas → split → treino com tracking → registro no registry → promoção por critério codificado → serving → player TUI que toca e emite eventos → event store. Retreino disparado manualmente, porém **reprodutível a partir de um commit e uma versão de dado**.

### 3.2 Fora, explicitamente

Simulador de usuários · recomendador · Jamendo/Audius · GUI desktop · A/B · detecção de drift · deploy em cloud · autenticação · multiusuário · orquestrador de pipelines · Prometheus/Grafana.

Nenhum desses foi esquecido; cada um é uma spec própria (§11). Este registro existe para que a fatia não inche pelo caminho.

### 3.3 Uma escolha que contraria o pedido original

O player desta spec é uma **TUI em Python (Textual)**, não uma GUI React/Tauri. Uma GUI custa semanas que não compram aprendizado de MLOps. A GUI é a Spec 6 e consumirá a mesma API HTTP — o que força a API a ter contrato limpo desde já.

---

## 4. Arquitetura de componentes

Monorepo, seis pacotes, dependências em uma direção só.

| Pacote | Responsabilidade | Não sabe nada sobre | Depende de |
|---|---|---|---|
| `catalog` | Ingere dump do FMA e normaliza; busca e leitura de faixas | Áudio, ML, HTTP | Postgres |
| `audio` | Arquivo de áudio → mel-espectrograma e metadados técnicos. Função pura, sem I/O de banco | Catálogo, ML, HTTP | numpy, librosa |
| `ml` | `(melspec, label)` → treino, avaliação, artefato | HTTP, banco, player | torch, mlflow |
| `serving` | URI do registry → `predict(...)` → distribuição de gêneros | Como o modelo foi treinado | mlflow registry |
| `api` | FastAPI: catálogo, busca, stream, eventos, predição. Orquestra; não contém regra de domínio | Detalhes de treino | todos acima |
| `player` | TUI: reprodução local, HTTP contra a `api`, emissão de eventos | Banco, ML, modelos | `api` (HTTP) |

**Testes de fronteira** (se deixarem de ser verdade, a fronteira vazou):

- `audio` é testável com um seno sintético de 440Hz, sem banco e sem rede.
- `ml` treina a partir de um diretório de arrays, sem saber que existe um catálogo.
- `catalog`, `audio` e `ml` nunca importam `api` — é o que permite o pipeline de treino rodar offline, em notebook ou job, sem subir servidor.

### Layout

```
youfy/
├── packages/{catalog,audio,ml,serving,api,player}/
├── pipelines/          # CLI Typer: ingest, featurize, split, train, evaluate
├── infra/              # docker-compose, migrations Alembic
├── data/               # audio/ (imutável), features/, splits/  — DVC
└── docs/superpowers/specs/
```

---

## 5. Fluxo de dados

### 5.1 Pipeline offline — cinco estágios, cada um idempotente e invocável isolado

| # | Estágio | Entrada → Saída | Ponto de atenção |
|---|---|---|---|
| 1 | `ingest` | dump FMA → Postgres (`tracks`, `artists`, `genres`, `track_genres`) + `data/audio/` | O FMA tem mp3 corrompidos conhecidos → `ingest_failures`, sem derrubar a execução |
| 2 | `featurize` | `data/audio/*.mp3` → `data/features/melspec/{id}.npy` | Retomável. Manifest com hash da config (sample rate, `n_mels`, `hop_length`): config mudou, cache invalida sozinho |
| 3 | `split` | catálogo → `splits/{train,val,test}.json` | Determinístico por seed, estratificado por gênero, **agrupado por artista** |
| 4 | `train` | melspecs + split → run MLflow → `youfy-genre-clf` v_N, stage `None` | Params, métricas, curvas e artefato no mesmo run |
| 5 | `evaluate` | modelo + test → promoção para `Production` ou rejeição | Gate manual, **critério codificado** |

**Split agrupado por artista.** Se o mesmo artista aparece em treino e teste, o modelo aprende timbre de produção em vez de gênero e a acurácia infla silenciosamente. É o erro clássico em MIR, e o FMA é particularmente sujeito a ele por ter muitas faixas por artista. Tratado como invariante testada (§8), não como boa intenção.

**Gate de promoção com critério codificado.** Mesmo acionado à mão nesta fatia, a regra vive em código e é executada, não julgada: promove se `macro_f1_novo >= macro_f1_campeao + 0.005` no split de teste — a margem de 0,5 p.p. evita promover em cima de ruído de seed. Sem campeão, promove se `macro_f1 >= 0.40`, bem acima do acaso de 0,125 para as 8 classes balanceadas. É o que torna o retreino automático da Spec 4 uma troca de gatilho em vez de uma reescrita.

### 5.2 Runtime

```
player ──HTTP──▶ api ──▶ catalog            (busca, metadados)
                  │
                  ├──▶ stream de áudio
                  ├──▶ events (append-only)  ◀── batch do player
                  └──▶ serving ──▶ registry (stage=Production)
                           │
                           └──▶ predictions (track_id, dist, model_version, ts)
```

**Toda predição grava a `model_version` que a produziu.** Custa uma coluna hoje e é impossível de retrofitar: sem isso não se consegue atribuir mudança de comportamento a troca de modelo, nem fazer análise retroativa quando o drift aparecer.

---

## 6. Stack

| Camada | Escolha | Raciocínio / descartado |
|---|---|---|
| Runtime | Python 3.11+, `uv` | `uv` pelo lockfile determinístico — reprodutibilidade é requisito, não conforto |
| Banco | Postgres 16 local (docker-compose) | **Descartado Supabase** (usado nos outros projetos do autor): esta fatia roda offline, sem custo e sem rede. Supabase volta à mesa se houver deploy |
| Migrations | Alembic | |
| Versionamento de dado | DVC, remote local | Versiona `data/features` e `splits`. Áudio bruto é imutável — rastreado por manifest + hash, não duplicado |
| Tracking + Registry | MLflow local, backend Postgres, artefatos em filesystem | **Descartado W&B**: é SaaS, e o objetivo é operar a infra de ML, não consumi-la pronta |
| Treino | PyTorch + torchaudio | |
| Features | librosa (offline) / torchaudio (em lote) | |
| API | FastAPI + Pydantic v2 | |
| Player | Textual + `python-vlc` | vlc resolve codec de mp3 sem atrito |
| Orquestração | CLI Typer (`youfy`) + Makefile como atalho fino | A CLI `youfy` é a interface canônica; os alvos de `make` são atalhos finos sobre ela, nunca lógica duplicada. **Descartado Dagster/Prefect por ora**: o retreino desta fatia é manual, e orquestrador agora seria cerimônia sem carga. Entra na Spec 4, com trabalho real para fazer |
| Testes | pytest + pytest-asyncio + hypothesis | |
| CI | GitHub Actions | lint, testes e pipeline ponta a ponta com micro-dataset |

---

## 7. Contratos duradouros

Curtos em linhas, longos em consequência: todo subprojeto futuro os consome, e ambos são caros de mudar depois.

### 7.1 Schema de evento

```
events  (append-only, sem UPDATE)
  event_id           uuid          PK        -- gerado no cliente
  session_id         uuid
  actor_id           text                    -- 'human:osfarias' | 'sim:u00412'
  actor_kind         enum                    -- human | simulated
  track_id           text          FK tracks
  event_type         enum                    -- play_start | pause | resume | seek | skip | complete
  ts                 timestamptz             -- relógio do cliente
  ingested_at        timestamptz             -- relógio do servidor
  position_ms        int
  track_duration_ms  int
  client_event_seq   int                     -- ordem dentro da sessão
  context            jsonb                   -- {surface, rank, model_version}
```

**`actor_id` + `actor_kind` já nesta fatia, apesar de o simulador só chegar na Spec 2.** É o que permitirá a população sintética coexistir com a escuta real sem migração e sem contaminação, e isolar `actor_kind='human'` a qualquer momento para o holdout. Retrofitar significaria migrar o event store inteiro.

**`context.surface` + `rank` + `model_version`, apesar de não haver recomendador.** Todo evento registra de onde a faixa veio e em que posição. Sem isso, avaliação off-policy é impossível: a correção de viés de exposição exige saber qual política serviu o item e em que rank.

**`ts` (cliente) separado de `ingested_at` (servidor).** O player bufferiza quando a API está fora. Com um campo só, perde-se a distinção entre "ouviu às 3h" e "sincronizou às 3h", e toda análise temporal fica errada.

**Evento bruto, nunca interpretado.** Não existe coluna `liked`. Existem `skip` com `position_ms` e `complete`. A definição de "gostou" vai mudar várias vezes (skip aos 4s e skip aos 27s não são o mesmo fenômeno) e precisa ser redefinível retroativamente sobre o dado original. Sinais derivados — `skip_early`, `completion_ratio`, repeat — vivem em *view*, não em coluna.

### 7.2 Artefato de modelo

```python
class GenreClassifier(Protocol):
    feature_spec: FeatureSpec   # sample_rate, n_mels, hop_length, n_frames
    classes: list[str]          # ordem canônica do vetor de saída
    def predict(self, melspec: np.ndarray) -> np.ndarray: ...  # (n_classes,)
```

**O artefato carrega a própria `FeatureSpec`.** O `serving` não tem permissão de assumir que sabe featurizar: lê a spec de dentro do modelo e **valida contra a config do featurizer na carga, recusando subir se divergir**.

Isso elimina o *training/serving skew*, a falha mais perniciosa de ML em produção — modelo treinado com `n_mels=128` servido com 96 não estoura nem loga erro, apenas fica silenciosamente pior. Converter isso em falha ruidosa na inicialização é barato agora e impagável depois.

Pelo mesmo motivo `classes` mora no artefato: a ordem do vetor de saída nunca pode depender de um dicionário externo que alguém reordena.

### 7.3 Superfície da API

```
GET  /tracks?q=&genre=&limit=     lista/busca
GET  /tracks/{id}                 metadados (+ gênero predito, se houver)
GET  /tracks/{id}/stream          audio/mpeg, com range requests
POST /events                      batch, idempotente por event_id
GET  /tracks/{id}/genre           {dist, model_version}  |  503
GET  /health                      inclui a model_version carregada
```

`POST /events` é idempotente por `event_id` (`ON CONFLICT DO NOTHING`) porque o buffer offline vai reenviar. `GET /tracks/{id}/genre` devolve **503 explícito** quando não há modelo em `Production` — nunca fallback silencioso, que é como se acumula dado envenenado sem ninguém perceber.

---

## 8. Estratégia de testes

Testes de software convencionais não cobrem os modos de falha de ML: um pipeline pode passar em 100% dos unitários e produzir um modelo inútil. Quatro camadas.

**1. Unitários determinísticos** — rápidos, sem banco e sem rede.
- `audio`: seno de 440Hz → pico no bin esperado; silêncio → energia ~0; shape determinístico dada a config.
- `catalog`: fixture de ~20 faixas; mp3 corrompido vai para `ingest_failures` sem derrubar a execução.
- `serving`: `FeatureSpec` divergente → recusa carregar (testa-se o modo de falha, não o caminho feliz).
- `split`: property-based — para qualquer catálogo gerado, `artistas(train) ∩ artistas(test) == ∅`; estratificação dentro de tolerância.
- `events`: reenvio do mesmo `event_id` não duplica.

**2. Contrato** — API contra schema Pydantic via httpx; 503 com registry vazio. Player contra API falsa: buffer offline acumula, sincroniza, **não perde nem duplica evento**. Protege o ativo mais difícil de reconstruir do projeto.

**3. Pipeline ponta a ponta em CI** — micro-dataset versionado (~60 faixas, 3 gêneros, clipes de 3s) atravessando `ingest → featurize → split → train (1 época) → evaluate → promote` em menos de dois minutos. Pega o que unitário não pega: incompatibilidade entre estágios, mudança de formato de artefato, quebra de contrato do registry.

**4. Propriedades de ML**

| Teste | O que pega |
|---|---|
| **Reprodutibilidade** — mesma seed + mesmo dado versionado → mesmo macro-F1 dentro de ±0,002 | Não-determinismo escondido (ordem de dataloader, cudnn) |
| **Overfit proposital** — 50 amostras até ~100% de acurácia de treino | Separa "modelo ruim" de "pipeline de dado quebrado" — diagnósticos completamente diferentes |
| **Rótulos embaralhados** — treino com labels shuffled deve dar acaso | Vazamento. Cobre sozinho a falha do split por artista |
| **Featurização idempotente** — mesmo arquivo duas vezes → bytes idênticos | Não-determinismo em feature extraction, que corrompe cache silenciosamente |

**Deliberadamente ausente:** acurácia mínima do modelo como gate de CI. O CI não tem dataset completo nem GPU; threshold de qualidade em CI vira teste intermitente que se aprende a ignorar, o que é pior que não ter. O gate de qualidade vive no estágio `evaluate`, rodado com intenção.

---

## 9. Modos de falha

Princípio: **falha de dado vira quarentena, falha de contrato vira ruído, falha de rede vira buffer.**

| Onde | Falha | Comportamento |
|---|---|---|
| `ingest` | mp3 corrompido, metadado faltando | Registra em `ingest_failures` e continua. Relatório final; se mais de 2% das faixas do dump falharem, sai com código de erro |
| `featurize` | faixa ilegível ou interrupção no meio de 8k | Marca e segue; reinício retoma pelo manifest, pulando o já feito |
| `train` | OOM, divergência | Run marcado FAILED no MLflow. **Nunca registra modelo parcial** |
| `evaluate` | novo modelo pior que o campeão | Não promove — é o sistema funcionando, não erro. Código de saída 0 e relatório |
| `serving` | sem modelo em `Production` | 503 explícito; `/health` degradado. Nunca chuta |
| `serving` | `FeatureSpec` divergente | Recusa iniciar. Ruidoso na carga em vez de silencioso na predição |
| `player` | API fora | Eventos para SQLite local; sincroniza com backoff. A reprodução não para |
| `api` | evento reenviado | `ON CONFLICT DO NOTHING`, responde 200 |

**Observabilidade magra de propósito:** logs estruturados em JSON e um comando `youfy doctor` reportando estado (versão do dado, modelo em `Production`, contagem de eventos, última run, saúde das dependências). Prometheus e Grafana entram na Spec 5, quando houver algo real para monitorar em vez de dashboards vazios.

---

## 10. Critérios de aceite

A fatia está pronta quando, partindo de uma máquina limpa:

1. `make setup && make ingest` popula o catálogo com as 8.000 faixas do `fma_small`, e `ingest_failures` está preenchida e reportada.
2. `make featurize` produz um melspec por faixa ingerida com sucesso; interromper e reexecutar retoma sem refazer trabalho.
3. `make split` gera splits cujo invariante de artista disjunto passa no teste.
4. `make train` produz um run no MLflow com params, métricas, curva de treino e artefato, e registra `youfy-genre-clf`.
5. `make evaluate` compara com o campeão e promove ou rejeita segundo o critério codificado.
6. `youfy play` abre a TUI, busca, toca uma faixa até o fim, e o evento `complete` aparece em `events` com `actor_kind='human'` e `context.surface='search'`.
7. Derrubar a API durante a reprodução não interrompe o áudio; ao voltar, os eventos bufferizados chegam sem perda e sem duplicata.
8. `GET /tracks/{id}/genre` devolve distribuição e `model_version`; com registry vazio, devolve 503.
9. Subir o `serving` com featurizer divergente do `FeatureSpec` do modelo falha na inicialização.
10. O pipeline ponta a ponta com micro-dataset passa em CI em menos de dois minutos.
11. Dois `make train` com a mesma seed e a mesma versão de dado produzem macro-F1 idêntico dentro de ±0,002.
12. O teste de rótulos embaralhados fica na faixa do acaso: macro-F1 ≤ 0,20 contra acaso de 0,125 para 8 classes balanceadas.

---

## 11. Roadmap dos subprojetos

| Spec | Tema | Por que nesta ordem |
|---|---|---|
| 1 | **Loop fechado mínimo** (este documento) | Prova que o ciclo gira; estabelece os contratos duradouros |
| 2 | Simulador de população | Vem **antes** do recomendador: sem população, o recomendador não é avaliável |
| 3 | Recomendador content-based + loop | Consome embeddings da Spec 1 e interações da Spec 2 |
| 4 | Retreino automático + orquestrador | Troca o gatilho manual da Spec 1; Dagster/Prefect entram aqui, com carga real |
| 5 | Monitoramento, drift e A/B | Usa o drift induzível do simulador para validar a própria detecção |
| 6 | GUI desktop | Consome a mesma API HTTP da Spec 1 |
| 7 | Catálogo ao vivo (Jamendo, Audius) | Amplia a fonte sem alterar contratos |

---

## 12. Riscos conhecidos

| Risco | Mitigação |
|---|---|
| A fatia fina vira protótipo permanente | Critérios de aceite verificáveis (§10) e specs seguintes já nomeadas (§11) |
| Autoengano com dado sintético | `actor_kind` no schema, holdout humano isolado, e o simulador nunca valida a si mesmo |
| `fma_small` pequeno demais para a CNN generalizar | Aceito: a métrica não é o objetivo desta fatia. Subir para `fma_medium` é trocar uma config |
| Escopo de MLOps inchar | Orquestrador e observabilidade explicitamente adiados (§3.2), com destino registrado |
| Vazamento silencioso no split | Invariante property-based + teste de rótulos embaralhados (§8) |
