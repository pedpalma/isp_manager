# isp_manager

Sistema OSS/BSS para provedor de internet (ISP), oferecendo descoberta, provisionamento e monitoramento de ONUs/ONTs em redes GPON.

> **Status:** em desenvolvimento (V1).

---

## Capacidades (V1)

- **Descoberta** de ONUs/ONTs não provisionadas na rede
- **Leitura de sinal óptico** (RX/TX) sob demanda e periódica
- **Provisionamento** de ONUs/ONTs com rollback em caso de falha
- **Auditoria completa** de comandos enviados às OLTs
- **Base para integração** com ERP IXC

## Stack

| Camada   | Tecnologia                                    |
| -------- | --------------------------------------------- |
| Backend  | Python 3.12, FastAPI, SQLAlchemy 2.0 (async)  |
| Worker   | Celery + Redis                                |
| Banco    | PostgreSQL 17                                 |
| Frontend | Next.js 15 (App Router), TypeScript, Tailwind |
| Infra    | Docker Compose, deploy em Proxmox             |

---

## Pré-requisitos

- **Docker** 24+ e **Docker Compose** v2
- **Make** (`build-essential` no Debian/Ubuntu)
- **Git**
- **Python 3.12** (opcional)
- **Node.js 20+** (opcional)

---

## Quickstart

Primeira execução:

```bash
git clone https://github.com/pedpalma/isp_manager.git
cd isp_manager
make setup
make rebuild
make up
make migrate
```

Acesso:

- API: <http://localhost:8000>
- Docs interativos: <http://localhost:8000/docs>
- Frontend: <http://localhost:3000>
- Postgres: `localhost:5432` (credenciais no `.env`)

Para parar:

```bash
make down
```

---

## Comandos principais

Todos os comandos disponíveis em `make help`. Os mais usados:

| Comando                        | O que faz                            |
| ------------------------------ | ------------------------------------ |
| `make up`                      | Sobe todos os serviços em background |
| `make down`                    | Para todos os serviços               |
| `make logs`                    | Exibe logs de todos os serviços      |
| `make logs-api`                | Logs só do backend                   |
| `make logs-worker`             | Logs só do worker Celery             |
| `make shell-api`               | Bash dentro do container da API      |
| `make shell-db`                | Console psql conectado ao banco      |
| `make migrate`                 | Aplica migrations pendentes          |
| `make migration m="descrição"` | Cria nova migration                  |
| `make test`                    | Executa suíte de testes              |
| `make lint`                    | Roda Ruff + mypy                     |
| `make format`                  | Formata código com Ruff              |
| `make rebuild`                 | Rebuild forçado das imagens          |

---

## Licença

Por enquanto, somente para uso interno. Versão comercial planejada em fork separado.

---
