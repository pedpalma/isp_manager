-- Migration 0004: índice único parcial em optical_alert_event.
-- Garante que só existe UM alerta 'open' por (onu_id, metric_name) ao mesmo tempo.
-- Worker faz upsert logico: se já existe alerta aberto para o par, apenas
-- atualiza value e mantém triggered_at. Sem o índice, leituras consecutivas
-- abrem duplicatas.

CREATE UNIQUE INDEX uq_optical_alert_open
    ON optical_alert_event (onu_id, metric_name)
    WHERE status = 'open';
