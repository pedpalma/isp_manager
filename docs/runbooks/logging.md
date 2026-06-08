# Runbook: Logging estruturado

## Visão geral

A API e o worker emitem logs estruturados em JSON via structlog. Cada linha é um objeto JSON com campos previsíveis, prontos para `jq`, ingestão futura em sistemas de log centralizados ou filtros simples por `grep`.

O frontend (Next.js) fica fora desta padronização. Limitação documentada no fim do documento.

## Campos sempre presentes

Toda linha de log de api e worker carrega no mínimo:

| Campo       | Tipo                | Exemplo                            | Origem                                           |
| ----------- | ------------------- | ---------------------------------- | ------------------------------------------------ |
| `timestamp` | string ISO-8601 UTC | `"2026-06-08T17:42:11.123456Z"`    | structlog `TimeStamper`                          |
| `level`     | string              | `"info"`, `"error"`                | structlog `add_log_level`                        |
| `event`     | string              | `"request.start"`, `"task.finish"` | mensagem passada para `.info()`, `.error()` etc. |
| `logger`    | string              | `"app.api.access"`                 | structlog `add_logger_name`                      |

Campos opcionais aparecem quando aplicáveis:

| Campo                                          | Quando aparece                                                                                                              |
| ---------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| `request_id`                                   | toda linha emitida durante o processamento de um request HTTP, ou da execução de uma task Celery disparada por esse request |
| `task_id`                                      | linhas emitidas pelo Celery worker durante a execução de uma task                                                           |
| `task_name`                                    | idem                                                                                                                        |
| `method`, `path`, `status_code`, `duration_ms` | linhas do `LoggingMiddleware` (`request.start`, `request.finish`, `request.error`)                                          |
| `exception`, `exc_info`                        | em logs de erro com stack trace                                                                                             |

## Eventos principais

### API

| `event`          | Quando dispara                 | Quem emite          |
| ---------------- | ------------------------------ | ------------------- |
| `app.startup`    | boot da aplicação concluído    | `app.main`          |
| `app.shutdown`   | shutdown gracioso              | `app.main`          |
| `request.start`  | antes de chamar a rota         | `LoggingMiddleware` |
| `request.finish` | após a rota retornar (sucesso) | `LoggingMiddleware` |
| `request.error`  | rota levantou exceção          | `LoggingMiddleware` |

### Worker

| `event`       | Quando dispara                   | Quem emite                |
| ------------- | -------------------------------- | ------------------------- |
| `task.start`  | task entrou em execução          | `app.core.celery_signals` |
| `task.finish` | task terminou (sucesso ou falha) | `app.core.celery_signals` |

## Pipeline padrão para ler logs

`make logs-json` encapsula o pipeline limpo:

```bash
docker compose logs -f --no-log-prefix --tail=100 api worker \
  | grep --line-buffered '^{' \
  | jq -c .
```

O que cada etapa faz:

- `--no-log-prefix`: remove o prefixo `isp_manager_api  |` que o compose injeta. Sem isso, `jq` quebra porque a linha não começa com `{`.
- `grep '^{'`: filtra linhas que começam com `{`. Descarta texto puro residual (ex.: a primeira linha do reloader do uvicorn em dev, antes do dictConfig ter sido aplicado).
- `--line-buffered` no grep: necessário com `-f`. Sem isso, o grep buferiza e o `jq` parece travado por minutos antes de soltar qualquer saída.
- `jq -c .`: reformata cada linha como JSON compacto. Útil para encadear novos filtros via pipe.

## Como achar logs de uma requisição específica

### Por request_id

Suponha que o frontend recebeu erro com header `X-Request-ID: abc123`. Para ver todos os logs daquele request (API + worker, se houver task disparada):

```bash
make logs-json | jq 'select(.request_id == "abc123")'
```

### Por nível

```bash
make logs-json | jq 'select(.level == "error")'
```

### Requests lentos

```bash
make logs-json | jq 'select(.event == "request.finish" and .duration_ms > 500)'
```

### Eventos do Celery

```bash
make logs-json | jq 'select(.event | startswith("task."))'
```

### Excluindo o ruído de healthcheck

O compose chama `/health` a cada 10 segundos para liveness. Para esconder:

```bash
make logs-json | jq 'select(.path != "/health")'
```

## Como o request_id se propaga

1. O frontend envia o header `X-Request-ID` no request (UUID gerado pelo cliente API).
2. `RequestIDMiddleware` lê o header. Valida que é UUID; senão gera um novo. Amarra o id em `structlog.contextvars`.
3. Toda linha logada durante o request inclui automaticamente `request_id`.
4. Se a rota disparar uma task Celery (`some_task.delay(...)`), o signal `before_task_publish` lê o id do contexto e o injeta nos headers da mensagem Celery.
5. No worker, o signal `task_prerun` lê o id do header da task e o amarra no contexto do processo do worker.
6. Os eventos `task.start` e `task.finish`, mais qualquer log emitido pelo código da task, saem com o mesmo `request_id`.
7. `task_postrun` limpa o contexto para o id não vazar para a próxima task processada pelo mesmo worker.
8. Na API, `RequestIDMiddleware` também limpa o contexto no `finally`, mesmo se a rota levantar exceção.

A resposta HTTP carrega `X-Request-ID` no header. O cliente do frontend lê via `expose_headers` configurado no `CORSMiddleware`.

## Arquitetura (resumo)

`app/core/logging.py` é o único ponto de verdade do formato. Três funções públicas relevantes:

- `configure_logging()`: chamada no startup da API (dentro de `create_app()`) e do worker (via signal `setup_logging` do Celery).
- `get_uvicorn_log_config()`: retorna o dictConfig do stdlib que o uvicorn aplica via `--log-config`. Cobre o intervalo entre o uvicorn subir e o `app.main:app` ser importado.
- `make_uvicorn_formatter()`: factory referenciada pelo dictConfig através de `"()": "app.core.logging.make_uvicorn_formatter"`. Devolve o mesmo `ProcessorFormatter` que `configure_logging()` instala.

As três funções convergem para `_build_formatter()` e `_build_pre_chain()` privados. Não há duplicação de configuração: mudar o formato exige mexer em um único lugar.

No container da API, o `command` no `docker-compose.yml` gera `/tmp/uvicorn_log.json` a partir de `get_uvicorn_log_config()` e passa para o uvicorn:

```bash
python /app/scripts/render_uvicorn_log_config.py > /tmp/uvicorn_log.json
exec uvicorn app.main:app ... --log-config /tmp/uvicorn_log.json
```

O JSON é regenerado a cada start do container; nunca fica desincronizado com o código.

## Teste rápido de fumaça

Com o ambiente subido (`make up`), em uma janela:

```bash
make logs-json
```

Em outra janela:

```bash
RID=$(uuidgen)
curl -s -X POST -H "X-Request-ID: $RID" http://localhost:8000/api/v1/diagnostics/echo-task | jq .
```

Esperado na janela do `make logs-json`: ver pelo menos quatro linhas com o MESMO `request_id` igual a `$RID`:

- `request.start` (api)
- `task.start` (worker)
- `task.finish` (worker)
- `request.finish` (api)

Para isolar:

```bash
make logs-json | jq "select(.request_id == \"$RID\")"
```

## Limitações conhecidas

### Frontend não emite logs estruturados

`next dev` e `next start` não expõem configuração de logging customizada que produza JSON. O frontend continua logando em texto plano. Aceito como limitação. Se um dia for preciso correlacionar via log do front:

- envio de telemetria via API customizada (sem mexer no Next),
- ou wrapper com `pino`/`winston` nos pontos críticos (rotas de API do Next, server-side), ingerindo separadamente.

### Banner inicial do uvicorn em dev pode ter linhas em texto puro

Em dev (`--reload`), o supervisor do uvicorn usa `watchfiles`. Em raros cenários de boot, a primeira linha do reloader pode sair antes do dictConfig estar totalmente aplicado, ou via stderr em formato texto. O pipeline padrão (`make logs-json`) filtra essas linhas com `grep '^{'`. Não polui ferramenta de busca. Em prod (sem `--reload`), o problema não existe.

### Logs do Postgres e Redis não são estruturados

Esses dois serviços usam formato nativo. Permanecem fora de `make logs-json`. Para consulta:

```bash
make logs-db
docker compose logs -f redis
```

### `jq` é dependência de host

`make logs-json` exige `jq` instalado no host. O target valida e falha cedo se não estiver presente.

- Ubuntu/Debian: `sudo apt install jq`
- macOS: `brew install jq`

## Recuperando contexto manualmente em Python

Útil quando um log precisa carregar `request_id` em um caminho de código que não passou pelos middlewares (ex.: jobs agendados manuais, debug em REPL):

```python
from app.core.logging import bind_request_id, clear_request_context, get_logger

bind_request_id("manual-debug-1")
log = get_logger(__name__)
log.info("debug.event", note="rodando fora do hot path")
clear_request_context()
```

## Pendências conhecidas (não bloqueantes do Marco 8)

- `LoggingMiddleware` loga `request.start`/`request.finish` para TODA rota, inclusive `/health`. O healthcheck do compose bate a cada 10 segundos. Em uma sessão de debug com `make logs-json`, isso gera ruído. Filtro recomendado por enquanto:
  ```bash
  make logs-json | jq 'select(.path != "/health")'
  ```
  Marco futuro: lista de paths a ignorar no logging de acesso (configurável via env).
