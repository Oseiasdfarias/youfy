# Guia de Início Rápido

Este guia descreve os passos para preparar o ambiente de desenvolvimento local e rodar as suítes de validação do Youfy.

---

## Pré-requisitos

- **Linux** (ou macOS com Docker)
- **Python 3.11+**
- **Docker e Docker Compose**
- **uv** (gerenciador de ambientes e pacotes Python)
- Bibliotecas de sistema para áudio: `libsndfile1`, `ffmpeg`

---

## Passo a Passo de Instalação

### 1. Clonar e Instalar Dependências

Utilize o `Makefile` para sincronizar o workspace monorepo com lockfile determinístico:

```bash
make setup
```

### 2. Inicializar o Banco de Dados

Suba o container Postgres 16 na porta mapeada `5433` (para evitar conflitos com instâncias locais existentes):

```bash
make up
```

Verifique a saúde do serviço:

```bash
docker compose ps
```

### 3. Rodar os Testes Automatizados

Execute toda a suíte unitária e de integração:

```bash
make test
```

### 4. Executar o Teste Ponta a Ponta

Valide o encadeamento dos estágios `ingest` $\rightarrow$ `featurize` $\rightarrow$ `split` com geração dinâmica de micro-dataset sintético:

```bash
make e2e
```

### 5. Verificar Qualidade de Código (Lint)

```bash
make lint
```
