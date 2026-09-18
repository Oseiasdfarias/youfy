# Invariantes de ML: Disjunção por Artista

Um dos erros mais comuns e silenciosos em *Music Information Retrieval* (MIR) é a contaminação de artistas entre os conjuntos de treino e teste (*artist leak*).

---

## Por que a Disjunção de Artista é Crítica?

Modelos de áudio convolucionais possuem capacidade suficiente para memorizar assinaturas acústicas de produção musical:
- Tipo de microfone e equalização do vocalista.
- Compressor de masterização ou estúdio de gravação.
- Estilo específico de sintetizador ou timbre de guitarra.

Se o mesmo artista estiver presente tanto no conjunto de treino quanto no de teste, o modelo aprenderá a reconhecer a assinatura de produção do artista em vez das características universais do gênero musical. Como consequência:
- A acurácia no conjunto de teste inflará artificialmente.
- O modelo falhará drasticamente quando submetido a faixas de novos artistas em produção.

---

## O Invariante Matemático

Para todo particionamento gerado pelo Youfy:

$$\text{artistas}(\text{train}) \cap \text{artistas}(\text{val}) = \emptyset$$
$$\text{artistas}(\text{train}) \cap \text{artistas}(\text{test}) = \emptyset$$
$$\text{artistas}(\text{val}) \cap \text{artistas}(\text{test}) = \emptyset$$

```mermaid
flowchart TD
    subgraph Catalog["Acervo Completo de Artistas - N Artistas Únicos"]
        Art["Artistas: A1, A2, A3, ... An"]
    end

    subgraph Splits["Partições 100% Estritas e Disjuntas"]
        Train["Conjunto de Treino - Train ~80%<br/>Artistas: A1, A4, A7, ..."]
        Val["Conjunto de Validação - Val ~10%<br/>Artistas: A2, A5, ..."]
        Test["Conjunto de Teste - Test ~10%<br/>Artistas: A3, A6, ..."]
    end

    Art --> Train
    Art --> Val
    Art --> Test

    Train <-.->|"Disjunção: Interseção Vazia"| Val
    Val <-.->|"Disjunção: Interseção Vazia"| Test
    Train <-.->|"Disjunção: Interseção Vazia"| Test

    classDef catalog fill:#18181b,stroke:#a855f7,stroke-width:1.5px,color:#f4f4f5;
    classDef train fill:#18181b,stroke:#3b82f6,stroke-width:1.5px,color:#60a5fa;
    classDef val fill:#18181b,stroke:#10b981,stroke-width:1.5px,color:#34d399;
    classDef test fill:#18181b,stroke:#f59e0b,stroke-width:1.5px,color:#fbbf24;
    class Catalog,Art catalog;
    class Train train;
    class Val val;
    class Test test;
```

---

## Implementação: Algoritmo Guloso por Déficit

A função `make_splits` no módulo `youfy_pipelines.split` opera da seguinte forma:

```mermaid
flowchart TD
    Start["Início: make_splits(tracks, seed, ratios)"] --> Group["1. Agrupar faixas por (gênero, artista)"]
    Group --> Quotas["2. Calcular cotas ideais de faixas por gênero e split"]
    Quotas --> LoopGenre{"Para cada gênero"}
    LoopGenre --> SortArtists["Ordenar artistas por contagem decrescente (com shuffle por seed)"]
    SortArtists --> LoopArtist{"Para cada artista"}
    LoopArtist --> CalcDeficit["Calcular déficit atual de faixas em Train, Val e Test"]
    CalcDeficit --> Assign["Atribuir TODAS as faixas do artista ao split com maior déficit"]
    Assign --> CheckArtist{"Mais artistas no gênero?"}
    CheckArtist -- Sim --> LoopArtist
    CheckArtist -- Não --> CheckGenre{"Mais gêneros?"}
    CheckGenre -- Sim --> LoopGenre
    CheckGenre -- Não --> AssertCheck["Verificar Invariante Matemático (assert sets disjuntos)"]
    AssertCheck --> Export["Exportar train.parquet, val.parquet, test.parquet"]

    classDef proc fill:#18181b,stroke:#3b82f6,stroke-width:1.5px,color:#f4f4f5;
    classDef cond fill:#27272a,stroke:#a855f7,stroke-width:1.5px,color:#f4f4f5;
    classDef out fill:#09090b,stroke:#10b981,stroke-width:2px,color:#34d399;
    class Start,Group,Quotas,SortArtists,CalcDeficit,Assign,AssertCheck proc;
    class LoopGenre,LoopArtist,CheckArtist,CheckGenre cond;
    class Export out;
```

1. Agrupa as faixas por par `(gênero, artista)`.
2. Calcula as cotas ideais de faixas para cada conjunto (`train: 70%`, `val: 15%`, `test: 15%`).
3. Para cada gênero:
   - Ordena os artistas pelo número de faixas (desempatando por um embaralhamento reprodutível via `--seed`).
   - Atribui **todas** as faixas de um artista ao conjunto cujo déficit de faixas daquele gênero for maior no momento.
4. Como cada artista é processado de forma atômica, a disjunção é garantida **por construção**.

---

## Validação Baseada em Propriedades (Hypothesis)

Além dos testes unitários convencionais, o Youfy executa testes de propriedades via **Hypothesis** (`test_propriedade_disjuncao_de_artista_vale_para_qualquer_acervo`):
- Gera dezenas de catálogos sintéticos com topologias extremas (artistas com muitas faixas, artistas com uma única faixa, distribuições desbalanceadas de gêneros).
- Valida que o invariante de disjunção se mantém rigorosamente verdadeiro para qualquer acervo arbitrário.

