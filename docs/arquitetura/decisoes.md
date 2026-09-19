# Decisões Estruturais & Fundamentos de Engenharia

Toda decisão de arquitetura no Youfy foi pensada para priorizar o aprendizado prático e a robustez de MLOps, evitando armadilhas comuns em projetos pessoais de IA.

---

## 1. Fonte de Catálogo: Por que o FMA e não o YouTube?

A concepção preliminar de utilizar raspagem ou APIs do YouTube foi descartada após análise rigorosa dos Termos de Serviço e Políticas de Desenvolvedor da plataforma:

```mermaid
flowchart TD
    subgraph S_YT["YouTube (Inviável)"]
        YT1["Termos de Serviço: Proíbe raspagem automatizada"]
        YT2["Dev Policy III.I.7-8: Proíbe separar componente de áudio"]
        YT3["Dev Policy III.I.9: Proíbe player em background"]
        YT4["Dev Policy III.E.4: Dados não retidos além de 30 dias"]
        YT5["Cota de API: 10.000 un/dia (100 buscas/dia)"]
    end

    subgraph S_FMA["Free Music Archive (FMA - Adotado)"]
        FMA1["Licenciamento Aberto Creative Commons"]
        FMA2["Benchmark MIR Acadêmico Consolidado"]
        FMA3["Conjunto fma_small: 8.000 faixas de 30s (~7.2 GB)"]
        FMA4["8 gêneros musicais perfeitamente balanceados"]
        FMA5["Dataset local, 100% offline, sem custos ou rede"]
    end

    classDef ytStyle stroke:#ef4444,stroke-width:2px;
    classDef fmaStyle stroke:#10b981,stroke-width:2px;
    class S_YT,YT1,YT2,YT3,YT4,YT5 ytStyle;
    class S_FMA,FMA1,FMA2,FMA3,FMA4,FMA5 fmaStyle;
```

### O que o Free Music Archive (FMA) viabiliza:
- **Reprodução Legal:** Arquivos MP3 armazenados localmente e tocados sem intermediários.
- **Métricas Comparáveis com a Literatura:** Acurácia e Macro-F1 diretamente comparáveis com papers de MIR (*Music Information Retrieval*).
- **Fatia Inicial Balanceada:** O `fma_small` possui exatamente 1.000 faixas para cada um dos 8 gêneros (Electronic, Experimental, Folk, Hip-Hop, Instrumental, International, Pop, Rock).

---

## 2. População Sintética + Holdout Real

Trabalhar com um único usuário humano gera um ciclo de MLOps estatisticamente anêmico:
- Sem potência estatística para testes A/B.
- Impossibilidade de exercitar *bandits* ou recomendação colaborativa.
- Ausência de volume para observar *drift* de distribuição.

```mermaid
flowchart TD
    subgraph S_Sim["População Sintética"]
        Sim["Simulador de Usuários"] -->|Sessões de Escuta| Batch["Lotes de Eventos"]
        Batch -->|actor_kind='simulated'| Events[("Event Store (Postgres)")]
    end

    subgraph S_Hum["Escuta Humana (Holdout Puro)"]
        User["Usuário Humano"] -->|Player TUI| RealEvent["Eventos Reais"]
        RealEvent -->|actor_kind='human'| Events
    end

    Events -->|Segregação Estrita| Eval["Avaliação e Benchmark Honestos"]

    classDef simStyle stroke:#3b82f6,stroke-width:2px;
    classDef humanStyle stroke:#10b981,stroke-width:2px;
    class Sim,Batch simStyle;
    class User,RealEvent humanStyle;
```

> [!IMPORTANT]
> A escuta humana real permanece como **holdout honesto**, nunca misturada com os dados sintéticos. Isso protege o projeto contra o autoengano de validar o simulador com o próprio simulador.

---

## 3. Arquitetura do Primeiro Modelo

Em vez de iniciar por representações auto-supervisionadas difíceis de calibrar ou recomendadores com dados esparsos:
- **Classificador de Gênero Supervisionado:** Rede Convolucional 2D (CNN) sobre mel-espectrogramas.
- **Rótulos Confiáveis:** Herdados da taxonomia de gêneros do FMA.
- **Reaproveitamento de Embeddings:** A penúltima camada da rede servirá diretamente como embedding acústico para o recomendador *content-based* futuro (Spec 3).

```mermaid
flowchart TD
    Audio["Áudio 30s"] --> Melspec["Mel-espectrograma (128, 1292)"]
    Melspec --> Conv["Camadas Convolucionais 2D + BatchNorm + ReLU"]
    Conv --> Pool["Adaptive Max/Avg Pooling"]
    Pool --> Penult["Penúltima Camada Linear (Embedding 256d)"]
    Penult --> Head["Classificador Linear (8 Classes)"]
    Head --> Pred["Probabilidades de Gênero (Softmax)"]

    classDef penultStyle stroke:#8b5cf6,stroke-width:2px;
    classDef predStyle stroke:#f97316,stroke-width:2px;
    class Penult penultStyle;
    class Pred predStyle;
```

---

## 4. Fatia Vertical Fina vs. Fundação Horizontal

```mermaid
flowchart TD
    subgraph S_FH["Armadilha: Fundação Horizontal"]
        FH1["Meses em infraestrutura e mensageria"] --> FH2["Nenhum modelo treinado"] --> FH3["Abandono do projeto"]
    end

    subgraph S_MP["Armadilha: Modelo Primeiro"]
        MP1["Centenas de Jupyter Notebooks soltos"] --> MP2["Código sem contratos nem testes"] --> MP3["Impossível de servir ou monitorar"]
    end

    subgraph S_YF["Abordagem Youfy: Fatia Vertical Fina"]
        Y1["Infra magra: Postgres local + TUI Textual"] --> Y2["Espinha de MLOps rigorosa: DVC + MLflow + Testes de Invariantes"] --> Y3["Ciclo de ponta a ponta comprovado no primeiro mês"]
    end

    S_FH -. "evitar" .-> S_MP
    S_MP -. "evitar" .-> S_YF

    classDef fhStyle stroke:#ef4444,stroke-width:2px;
    classDef mpStyle stroke:#f59e0b,stroke-width:2px;
    classDef yfStyle stroke:#10b981,stroke-width:2px;
    class S_FH,FH1,FH2,FH3 fhStyle;
    class S_MP,MP1,MP2,MP3 mpStyle;
    class S_YF,Y1,Y2,Y3 yfStyle;
```
