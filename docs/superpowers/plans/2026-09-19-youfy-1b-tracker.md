# Plano de Implementação Youfy 1B: Modelo e Serving (Subagent-Driven)

Este plano implementa a Spec 1B (`docs/superpowers/plans/2026-09-19-youfy-1b-modelo-e-serving.md`) utilizando a abordagem rigorosa orientada a subagentes (TDD RED -> GREEN -> REFACTOR e verificação ponta a ponta).

## Regras Globais & Diretrizes
1. Mensagens de commit limpas, sem menção a IA.
2. Não alterar indentação nem formatar código existente sem necessidade funcional.
3. Fronteiras estritas:
   - `packages/ml` não importa `catalog`, `serving` nem `pipelines`.
   - `packages/serving` não sabe como o modelo foi treinado.
   - `pipelines` é a única camada de orquestração CLI.
4. Branch de trabalho: `plano/1b-modelo-e-serving`.
5. Binário `uv` exportado: `export PATH="/home/osfarias/workspace/workspace_think/youfy/.bin:$PATH"`.
6. Postgres e MLflow locais rodando no compose (5433 para Postgres, 5000 para MLflow).

## Tarefas do Plano 1B

- [ ] **Task 1: MLflow local e o contrato do artefato**
  - Scaffold de `packages/ml` e teste `packages/ml/tests/test_artifact.py` (RED).
  - Implementação de `GenreClassifier` Protocol e `TorchGenreClassifier` em `packages/ml/src/youfy_ml/artifact.py` (GREEN).
  - Docker compose com serviço MLflow em banco `mlflow` segregado, alvos Makefile `mlflow-db` e `mlflow-up`.
  - Verificação com `curl -sf http://localhost:5000/health`, lint e testes. Commit.

- [ ] **Task 2: `ml.dataset` — leitura dos arrays com rótulos**
  - Testes em `packages/ml/tests/test_dataset.py` (RED).
  - Implementação de `MelDataset` e `collate_fn` em `packages/ml/src/youfy_ml/dataset.py` (GREEN).
  - Testes com DataLoader, determinismo e shape. Commit.

- [ ] **Task 3: `ml.model` — a CNN e o semeador determinístico**
  - Testes em `packages/ml/tests/test_model.py` (RED).
  - Implementação de `GenreCNN` e função `seed_everything` em `packages/ml/src/youfy_ml/model.py` (GREEN).
  - Embeddings 256d na penúltima camada preservados para recomendador futuro. Commit.

- [ ] **Task 4: `ml.train` — loop de treino e as duas propriedades de ML**
  - Testes em `packages/ml/tests/test_train.py` (RED):
    - Overfit proposital em 50 amostras (~100% acurácia).
    - Reprodutibilidade estrita com mesma seed (±0.002 macro-F1).
  - Implementação de `train_one_epoch`, `fit` e callbacks de métricas em `packages/ml/src/youfy_ml/train.py` (GREEN). Commit.

- [ ] **Task 5: `ml.evaluate` — métricas e o teste de rótulos embaralhados**
  - Testes em `packages/ml/tests/test_evaluate.py` (RED):
    - Rótulos embaralhados com 8 classes balanceadas resultando em macro-F1 ≤ 0.20 (acaso = 0.125).
  - Implementação de `evaluate` com cálculo de acurácia, loss e Macro-F1 em `packages/ml/src/youfy_ml/evaluate.py` (GREEN). Commit.

- [ ] **Task 6: `ml.promotion` — o gate codificado**
  - Testes em `packages/ml/tests/test_promotion.py` (RED).
  - Implementação de `should_promote(candidate_metrics, champion_metrics)` em `packages/ml/src/youfy_ml/promotion.py` (GREEN):
    - Sem campeão: `macro_f1 >= 0.40`.
    - Com campeão: `macro_f1_novo >= macro_f1_campeao + 0.005`. Commit.

- [ ] **Task 7: `ml.tracking` — run do MLflow e registro por alias**
  - Testes em `packages/ml/tests/test_tracking.py` (RED) com SQLite backend de teste.
  - Implementação de `log_training_run` e `promote_model_to_production` em `packages/ml/src/youfy_ml/tracking.py` (GREEN).
  - Uso de alias `production` (compatível com MLflow 2.9+). Commit.

- [ ] **Task 8: `serving` — carga do registry com validação de FeatureSpec**
  - Scaffold de `packages/serving` e testes em `packages/serving/tests/test_loader.py` (RED):
    - Falha ruidosa ao carregar quando `FeatureSpec` diverge.
    - Sucesso e predição correta quando `FeatureSpec` casa.
  - Implementação de `ModelRegistryLoader` e `ServingPredictor` em `packages/serving/src/youfy_serving/` (GREEN). Commit.

- [ ] **Task 9: CLI `train` e `evaluate`, e2e do 1B e CI**
  - Comandos `youfy pipeline train` e `youfy pipeline evaluate` em `pipelines/src/youfy_pipelines/cli.py`.
  - Testes e2e em `pipelines/tests/test_pipeline_e2e.py` cobrindo o ciclo completo até promoção.
  - Atualização do `Makefile` e `.github/workflows/ci.yml`. Commit final e validação geral.

