# Guia Prático: Treino e Serving

Este guia demonstra como treinar o classificador convolucional de gênero musical, acompanhar experimentos no MLflow local, submeter modelos ao gate codificado de promoção e utilizá-los no serving com detecção automática de divergência (*training/serving skew*).

---

## 1. Pré-requisitos e Ambiente

Certifique-se de que os containers do Postgres e do MLflow estão operacionais:

```bash
# Iniciar Postgres e MLflow local (porta 5000)
make up
make mlflow-up

# Verificar saúde do MLflow
curl -sf http://localhost:5000/health
```

A interface web do MLflow estará acessível em `http://localhost:5000`.

---

## 2. Execução do Treinamento

O comando `train` lê os splits gerados em `data/splits/<fingerprint>/` e as matrizes em `data/features/melspec/<fingerprint>/`:

```bash
# Treino padrão (10 épocas, batch size 32, seed 42)
youfy pipeline train --epochs 10 --batch-size 32 --seed 42
```

Saída estruturada emitida:
```json
{"event": "train.concluido", "run_id": "9a2f1b8c...", "versao": "1", "val_macro_f1": 0.5421}
```

O comando:
1. Executa o loop de treino determinístico com a arquitetura `GenreCNN`.
2. Calcula loss e métricas de validação a cada época.
3. Registra parâmetros, métricas e o artefato no experimento `youfy-genre` do MLflow.
4. Registra a versão recém-criada no **Model Registry** do MLflow sob o nome `youfy-genre-cnn`.

---

## 3. Avaliação e Gate de Promoção

Para que uma versão seja consumida em produção, ela deve passar pelo gate de promoção codificado:

```bash
# Avaliar a versão 1 contra o campeão vigente
youfy pipeline evaluate --version 1 --margin 0.005 --floor 0.40
```

### Regras do Gate:
1. **Primeiro modelo (sem campeão prévio)**:
   - Se $\text{Macro-F1} \ge 0.40$, o modelo é aprovado e recebe o alias `production`.
   - Se $\text{Macro-F1} < 0.40$, a promoção é recusada (`motivo=abaixo_do_piso`).
2. **Modelo subsequente (com campeão ativo)**:
   - O novo modelo precisa superar o campeão por uma margem mínima:
     $$\text{Macro-F1}_{\text{challenger}} \ge \text{Macro-F1}_{\text{champion}} + 0.005$$
   - Ganhos inferiores a $+0.005$ são rejeitados para evitar que oscilações aleatórias decorrentes de seeds desestabilizem a produção (`motivo=ganho_insuficiente`).

---

## 4. Consumo no Serving e Prevenção de Skew

Uma vez promovido com o alias `production`, o modelo é carregado pelo `youfy-serving`:

```python
from youfy_audio.spec import FeatureSpec
from youfy_serving.loader import load_production
from youfy_serving.predictor import Predictor

# A aplicação declara a especificação que produz
spec = FeatureSpec(sample_rate=22050, n_mels=128, hop_length=512, n_frames=1292)

# Carrega a versão 'production' validando a spec
classificador = load_production(
    tracking_uri="http://localhost:5000",
    model_name="youfy-genre-cnn",
    expected_spec=spec,
)

preditor = Predictor(classificador)
```

### Comportamento em Caso de Incompatibilidade

Se o modelo tiver sido treinado, por exemplo, com `n_mels=64` ou `n_frames=600`, o `load_production` lança imediatamente uma exceção:

```text
youfy_serving.errors.FeatureSpecMismatch: FeatureSpec divergente no campo 'n_mels': esperado=128, encontrado=64
```

Isso impede que o serviço entre no ar em estado corrompido, garantindo consistência matemática absoluta entre as matrizes de entrada e o modelo em execução.
