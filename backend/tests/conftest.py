import os

os.environ.setdefault("ISP_APP_DB_PASSWORD", "test-app-pass")
os.environ.setdefault("ISP_MIGRATOR_DB_PASSWORD", "test-migrator-pass")
os.environ.setdefault("API_SECRET_KEY", "x" * 48)
os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("LOG_FORMAT", "json")
# Secret usado pelos testes de coleta.
os.environ.setdefault("PYTEST_OLT_SECRET", "pytest-fake-pass")
# Força adapter mock em qualquer cenário de teste.
os.environ.setdefault("COLLECTION_OLT_ADAPTER", "mock")


import pytest  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.api.errors import register_error_handlers  # noqa: E402
from app.api.middleware.logging import LoggingMiddleware  # noqa: E402
from app.api.middleware.request_id import RequestIDMiddleware  # noqa: E402
from app.core.exceptions import ConflictError, NotFoundError  # noqa: E402
from app.core.logging import configure_logging, get_request_id  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _logging() -> None:
    # Garante o pipeline de logging configurado (e passa pelo self-test).
    configure_logging()


@pytest.fixture(scope="session", autouse=True)
def _celery_eager() -> None:
    """task_always_eager=True faz .delay() rodar SÍNCRONO no mesmo
    processo do teste, permitindo asserts imediatos sobre o estado do
    job pós-POST. task_eager_propagates=True faz exceptions
    estourarem no teste em vez de serem engolidas (defensivo)."""
    from app.celery_app import celery_app

    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = True


def _build_app() -> FastAPI:
    app = FastAPI()
    # Mesma ordem do main.py real: logging primeiro, request_id depois
    app.add_middleware(LoggingMiddleware)
    app.add_middleware(RequestIDMiddleware)
    register_error_handlers(app)

    @app.get("/ok")
    def ok():
        return {"ok": True}

    @app.get("/whoami")
    def whoami():
        # Prova que o request_id amarrado pelo middleware está disponível ao handler.
        return {"request_id": get_request_id()}

    @app.get("/notfound")
    def notfound():
        raise NotFoundError("ONU não encontrada.", details={"serial": "ABC123"})

    @app.get("/conflict")
    def conflict():
        raise ConflictError("Serial já provisionado.")

    @app.get("/needint")
    def needint(n: int):
        return {"n": n}

    @app.get("/boom")
    def boom():
        raise RuntimeError("explosão inesperada")

    return app


@pytest.fixture()
def client() -> TestClient:
    # raise_server_exceptions=False
    return TestClient(_build_app(), raise_server_exceptions=False)


PYTEST_PREFIX = "pytest-"


def _try_inventory_cleanup() -> None:
    """Best-effort: deleta registros com prefixo `pytest-` em toda a pilha.
    Ordem: optical -> provisioning -> collection -> auth -> inventory.
    Silencioso em qualquer erro (banco fora, schema inexistente, etc.)."""
    try:
        from sqlalchemy import create_engine, text  # noqa: PLC0415

        from app.core.config import settings as _settings  # noqa: PLC0415

        engine = create_engine(_settings.database.build_app_sync_url())
        try:
            with engine.connect() as conn, conn.begin():
                # Alertas cujas ONUs pertencem a OLTs de teste.
                conn.execute(
                    text(
                        """
                        DELETE FROM optical_alert_event
                        WHERE onu_id IN (
                            SELECT o.onu_id
                            FROM onu o
                            JOIN pon_port pp ON pp.pon_port_id = o.pon_port_id
                            JOIN slot s ON s.slot_id = pp.slot_id
                            JOIN chassis c ON c.chassis_id = s.chassis_id
                            JOIN olt ol ON ol.olt_id = c.olt_id
                            WHERE ol.name LIKE :p
                        )
                        """
                    ),
                    {"p": f"{PYTEST_PREFIX}%"},
                )
                # optical_reading é particionada por collected_at; DELETE no pai
                # propaga para todas as partições automaticamente.
                conn.execute(
                    text(
                        """
                        DELETE FROM optical_reading
                        WHERE onu_id IN (
                            SELECT o.onu_id
                            FROM onu o
                            JOIN pon_port pp ON pp.pon_port_id = o.pon_port_id
                            JOIN slot s ON s.slot_id = pp.slot_id
                            JOIN chassis c ON c.chassis_id = s.chassis_id
                            JOIN olt ol ON ol.olt_id = c.olt_id
                            WHERE ol.name LIKE :p
                        )
                        """
                    ),
                    {"p": f"{PYTEST_PREFIX}%"},
                )
                # Zera todas as policies: testes que dependem delas criam as suas.
                # Scope global não é distinguido intencionalmente: policies vazam
                # entre testes se não limpar tudo.
                conn.execute(text("DELETE FROM optical_threshold_policy"))

                # provisioning - ORDEM DE DEPENDÊNCIA:
                # rollback -> step -> order -> normalized_command -> template.
                # provisioning_rollback e provisioning_step referenciam
                # provisioning_order; provisioning_step tem ON DELETE CASCADE
                # mas removemos explicitamente por clareza e simetria.
                conn.execute(
                    text(
                        """
                        DELETE FROM provisioning_rollback
                        WHERE provisioning_order_id IN (
                            SELECT po.provisioning_order_id
                            FROM provisioning_order po
                            JOIN olt ol ON ol.olt_id = po.olt_id
                            WHERE ol.name LIKE :p
                        )
                        """
                    ),
                    {"p": f"{PYTEST_PREFIX}%"},
                )
                conn.execute(
                    text(
                        """
                        DELETE FROM provisioning_step
                        WHERE provisioning_order_id IN (
                            SELECT po.provisioning_order_id
                            FROM provisioning_order po
                            JOIN olt ol ON ol.olt_id = po.olt_id
                            WHERE ol.name LIKE :p
                        )
                        """
                    ),
                    {"p": f"{PYTEST_PREFIX}%"},
                )
                conn.execute(
                    text(
                        """
                        DELETE FROM provisioning_order
                        WHERE olt_id IN (
                            SELECT olt_id FROM olt WHERE name LIKE :p
                        )
                        """
                    ),
                    {"p": f"{PYTEST_PREFIX}%"},
                )
                conn.execute(
                    text(
                        """
                        DELETE FROM normalized_command
                        WHERE manufacturer_id IN (
                            SELECT manufacturer_id FROM manufacturer
                            WHERE slug LIKE :p
                        )
                        """
                    ),
                    {"p": f"{PYTEST_PREFIX}%"},
                )
                conn.execute(
                    text(
                        """
                        DELETE FROM provisioning_template
                        WHERE manufacturer_id IN (
                            SELECT manufacturer_id FROM manufacturer
                            WHERE slug LIKE :p
                        )
                        """
                    ),
                    {"p": f"{PYTEST_PREFIX}%"},
                )

                # collection
                conn.execute(
                    text(
                        """
                        DELETE FROM collection_log WHERE olt_id IN (
                            SELECT olt_id FROM olt WHERE name LIKE :p
                        )
                        """
                    ),
                    {"p": f"{PYTEST_PREFIX}%"},
                )
                conn.execute(
                    text(
                        """
                        DELETE FROM pending_onu WHERE olt_id IN (
                            SELECT olt_id FROM olt WHERE name LIKE :p
                        )
                        """
                    ),
                    {"p": f"{PYTEST_PREFIX}%"},
                )
                conn.execute(
                    text(
                        """
                        DELETE FROM collection_job WHERE olt_id IN (
                            SELECT olt_id FROM olt WHERE name LIKE :p
                        )
                        """
                    ),
                    {"p": f"{PYTEST_PREFIX}%"},
                )

                # auth
                # Sessões primeiro (FK CASCADE de app_user, mas removemos
                # explicitamente por clareza), depois usuários, depois grupos.
                conn.execute(
                    text(
                        """
                        DELETE FROM app_user_session WHERE app_user_id IN (
                            SELECT app_user_id FROM app_user WHERE username LIKE :p
                        )
                        """
                    ),
                    {"p": f"{PYTEST_PREFIX}%"},
                )
                conn.execute(
                    text("DELETE FROM app_user WHERE username LIKE :p"),
                    {"p": f"{PYTEST_PREFIX}%"},
                )
                conn.execute(
                    text("DELETE FROM user_group WHERE name LIKE :p"),
                    {"p": f"{PYTEST_PREFIX}%"},
                )

                # inventory
                # ONU: deletar ANTES de pon_port e onu_model,
                # que a ONU referencia. onu_runtime_state cascateia no hard
                # delete da ONU, mas removemos explicitamente por clareza.
                conn.execute(
                    text(
                        """
                        DELETE FROM onu_runtime_state WHERE onu_id IN (
                            SELECT o.onu_id
                            FROM onu o
                            JOIN pon_port pp ON pp.pon_port_id = o.pon_port_id
                            JOIN slot s ON s.slot_id = pp.slot_id
                            JOIN chassis c ON c.chassis_id = s.chassis_id
                            JOIN olt ol ON ol.olt_id = c.olt_id
                            WHERE ol.name LIKE :p
                        )
                        """
                    ),
                    {"p": f"{PYTEST_PREFIX}%"},
                )
                conn.execute(
                    text(
                        """
                        DELETE FROM onu WHERE pon_port_id IN (
                            SELECT pp.pon_port_id
                            FROM pon_port pp
                            JOIN slot s ON s.slot_id = pp.slot_id
                            JOIN chassis c ON c.chassis_id = s.chassis_id
                            JOIN olt ol ON ol.olt_id = c.olt_id
                            WHERE ol.name LIKE :p
                        )
                        """
                    ),
                    {"p": f"{PYTEST_PREFIX}%"},
                )

                # Topologia: cascateia pelo nome da OLT pai.
                conn.execute(
                    text(
                        """
                        DELETE FROM pon_port WHERE slot_id IN (
                            SELECT s.slot_id
                            FROM slot s
                            JOIN chassis c ON c.chassis_id = s.chassis_id
                            JOIN olt o ON o.olt_id = c.olt_id
                            WHERE o.name LIKE :p
                        )
                        """
                    ),
                    {"p": f"{PYTEST_PREFIX}%"},
                )
                conn.execute(
                    text(
                        """
                        DELETE FROM slot WHERE chassis_id IN (
                            SELECT c.chassis_id
                            FROM chassis c
                            JOIN olt o ON o.olt_id = c.olt_id
                            WHERE o.name LIKE :p
                        )
                        """
                    ),
                    {"p": f"{PYTEST_PREFIX}%"},
                )
                conn.execute(
                    text(
                        """
                        DELETE FROM chassis WHERE olt_id IN (
                            SELECT olt_id FROM olt WHERE name LIKE :p
                        )
                        """
                    ),
                    {"p": f"{PYTEST_PREFIX}%"},
                )

                # Perfis e VLANs: filhas de olt.
                conn.execute(
                    text(
                        """
                        DELETE FROM vlan WHERE olt_id IN (
                            SELECT olt_id FROM olt WHERE name LIKE :p
                        )
                        """
                    ),
                    {"p": f"{PYTEST_PREFIX}%"},
                )
                conn.execute(
                    text(
                        """
                        DELETE FROM line_profile WHERE olt_id IN (
                            SELECT olt_id FROM olt WHERE name LIKE :p
                        )
                        """
                    ),
                    {"p": f"{PYTEST_PREFIX}%"},
                )
                conn.execute(
                    text(
                        """
                        DELETE FROM service_profile WHERE olt_id IN (
                            SELECT olt_id FROM olt WHERE name LIKE :p
                        )
                        """
                    ),
                    {"p": f"{PYTEST_PREFIX}%"},
                )

                # Catálogo / inventário direto.
                conn.execute(
                    text("DELETE FROM onu_model WHERE model LIKE :p"),
                    {"p": f"{PYTEST_PREFIX}%"},
                )
                conn.execute(
                    text("DELETE FROM olt WHERE name LIKE :p"),
                    {"p": f"{PYTEST_PREFIX}%"},
                )
                conn.execute(
                    text("DELETE FROM olt_model WHERE model LIKE :p"),
                    {"p": f"{PYTEST_PREFIX}%"},
                )
                conn.execute(
                    text("DELETE FROM credential WHERE label LIKE :p"),
                    {"p": f"{PYTEST_PREFIX}%"},
                )
                conn.execute(
                    text("DELETE FROM manufacturer WHERE slug LIKE :p"),
                    {"p": f"{PYTEST_PREFIX}%"},
                )
        finally:
            engine.dispose()
    except Exception:
        return


@pytest.fixture(scope="session", autouse=True)
def _inventory_cleanup_session_scope():
    """Limpa antes E depois da sessão. Limpar antes evita interferência de
    runs anteriores que tenham crashado no meio."""
    _try_inventory_cleanup()
    yield
    _try_inventory_cleanup()


@pytest.fixture(autouse=True)
def _optical_policy_cleanup_per_test():
    """Limpa optical_alert_event + optical_threshold_policy ANTES de cada
    teste. Sem isso, policies criadas em test_X vazam para test_Y e
    disparam 409 em testes que dependem de unicidade (scope_type,
    metric_name).

    optical_alert_event tem FK NOT NULL para policy_id; precisa ser
    apagado ANTES de optical_threshold_policy.

    Best-effort: silencioso em qualquer erro. Se o banco estiver
    indisponível, deixa estourar no próprio teste."""
    try:
        from sqlalchemy import create_engine, text  # noqa: PLC0415

        from app.core.config import settings as _settings  # noqa: PLC0415

        engine = create_engine(_settings.database.build_app_sync_url())
        try:
            with engine.connect() as conn, conn.begin():
                conn.execute(text("DELETE FROM optical_alert_event"))
                conn.execute(text("DELETE FROM optical_threshold_policy"))
        finally:
            engine.dispose()
    except Exception:
        pass
    yield
    # Pos-test: não limpa de novo. A próxima invocação desta fixture
    # cuida disso. Evita custo duplicado.


@pytest.fixture(autouse=True)
def _provisioning_command_cache_reset():
    """Zera o cache in-process de normalized_command entre testes.

    O worker mantém um singleton de módulo (_COMMAND_CACHE) com TTL 60s.
    Sem reset, um teste que cacheia comando de outra OLT/manufacturer
    pode influenciar um teste subsequente que espere resolução do zero.

    Best-effort: se o módulo não existir (test unit sem app carregada),
    silencioso."""
    try:
        from app.domains.provisioning.services import (  # noqa: PLC0415
            provisioning_worker,
        )

        provisioning_worker._COMMAND_CACHE.clear()
    except Exception:
        pass
    yield


@pytest.fixture(scope="session")
def real_client():
    """TestClient da aplicação real. O `with` aciona o lifespan: startup
    chama init_engine() (conecta no Postgres), shutdown chama dispose_engine()."""
    # Import lazy: evita carregar app.main no momento do collect do pytest.
    from app.main import create_app  # noqa: PLC0415

    app = create_app()
    with TestClient(app) as c:
        yield c
