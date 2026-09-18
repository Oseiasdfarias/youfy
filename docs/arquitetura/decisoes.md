# Decisões Estruturais

Toda decisão de arquitetura no Youfy foi pensada para priorizar o aprendizado prático e a robustez de MLOps, evitando armadilhas comuns em projetos pessoais de IA.

---

## 1. Fonte de Catálogo Aberta (FMA vs. YouTube)

A concepção preliminar de utilizar raspagem ou APIs do YouTube foi descartada após análise rigorosa dos Termos de Serviço e Políticas de Desenvolvedor da plataforma:

- **Restrições de Termos de Serviço:** Proibição explícita de extração e separação de faixas de áudio do componente de vídeo (Seção III.I.7-8).
- **Proibição de Background Player:** Impossibilidade de execução em segundo plano ou simulação de player de áudio dedicado.
- **Retenção de Dados:** Limitação de armazenamento de dados da API em até 30 dias (inviabilizando criação de conjuntos de dados longitudinais).
- **Cotas Severas:** Cota padrão de 10.000 unidades/dia (apenas 100 buscas/dia).

### Solução Adotada
O Youfy adota o **Free Music Archive (FMA)** como fonte primária:
- Catálogo livre sob licenças Creative Commons.
- Benchmark acadêmico consolidado em *Music Information Retrieval* (MIR), viabilizando comparação direta das métricas do modelo com a literatura especializada.
- Conjunto `fma_small`: 8.000 faixas de 30 segundos, distribuídas equilibradamente em 8 gêneros musicais (~7,2 GB).

---

## 2. Sinal de Interação: População Sintética + Holdout Real

Trabalhar com um único usuário humano gera um ciclo de MLOps estatisticamente anêmico:
- Não há potência estatística para testes A/B.
- É impossível exercitar algoritmos de recomendação colaborativa ou *multi-armed bandits*.
- A detecção de drift não tem sinal com volume suficiente.

### Solução Adotada
1. **População Sintética (Simulador):** Agentes com distribuições de preferências latentes geram logs de escuta contínuos, possibilitando experimentação estatística em larga escala.
2. **Holdout Humano Honesto:** Escutas humanas reais são marcadas e mantidas estritamente segregadas no schema (`actor_kind='human'`), garantindo que o simulador nunca seja avaliado contra si mesmo.

---

## 3. Primeiro Modelo: Classificador de Gênero Supervisionado

Em vez de iniciar por recomendadores complexos ou representações auto-supervisionadas difíceis de calibrar:
- **CNN 2D leve** sobre mel-espectrogramas.
- Rótulos supervisionados derivados diretamente da taxonomia do FMA.
- O objetivo primário é exercitar rapidamente o ciclo completo: treino, tracking de parâmetros no MLflow, registro de modelo, promoção por métrica codificada e serving com validação de contrato.
- A penúltima camada da rede servirá futuramente como extrator de embeddings acústicos para sistemas de recomendação.

---

## 4. Fatia Vertical Fina vs. Fundação Horizontal

Evitou-se a armadilha do "encanamento infinito" (meses criando infraestrutura sem treinar nada) e do "repositório de notebooks" (treino desconectado de engenharia de software):
- Cada camada funcional é implementada com espessura fina (TUI minimalista, API direta, banco local).
- **Exceção de alto investimento:** A espinha dorsal de dados, versionamento (DVC), tracking (MLflow), isolamento de features e testes de invariantes nasce com rigor absoluto desde o primeiro dia.
