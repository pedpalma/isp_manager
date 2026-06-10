<h1 align="center">ISP Manager</h1>

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

| Camada   | Tecnologia                                                                                                                                                                                                                                                                                                               |
| -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Backend  | ![Python](https://img.shields.io/badge/Python-3776AB?style=flat&logo=python&logoColor=white) ![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat&logo=fastapi&logoColor=white) ![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-D71F00?style=flat&logo=sqlalchemy&logoColor=white)                    |
| Worker   | ![Celery](https://img.shields.io/badge/Celery-37814A?style=flat&logo=celery&logoColor=white) ![Redis](https://img.shields.io/badge/Redis-DC382D?style=flat&logo=redis&logoColor=white)                                                                                                                                   |
| Banco    | ![PostgreSQL17](https://img.shields.io/badge/PostgreSQL-336791?style=flat&logo=postgresql&logoColor=white)                                                                                                                                                                                                               |
| Frontend | ![Next.js](https://img.shields.io/badge/Next.js-000000?style=flat&logo=nextdotjs&logoColor=white) ![TypeScript](https://img.shields.io/badge/TypeScript-3178C6?style=flat&logo=typescript&logoColor=white) ![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS-06B6D4?style=flat&logo=tailwindcss&logoColor=white) |
| Infra    | ![Docker](https://img.shields.io/badge/Docker-2496ED?style=flat&logo=docker&logoColor=white) ![Proxmox](https://img.shields.io/badge/Proxmox-E57000?style=flat&logo=proxmox&logoColor=white) ![Linux](https://img.shields.io/badge/Linux-FCC624?style=flat&logo=linux&logoColor=black)                                   |

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
