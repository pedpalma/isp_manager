-- Migration 0005: privilégio elevado para gestão de partições.

-- A 0001 criou create_optical_reading_partition como função normal
-- (roda como o caller). O role isp_app, usado pelas tasks Celery em
-- runtime, NÃO tem privilégio para CREATE TABLE em public por design
-- (isolamento de DDL contra SQL injection). Sem SECURITY DEFINER, a
-- task ensure_optical_partitions falha com "permission denied for
-- schema public".

-- ALTER FUNCTION já existente para SECURITY DEFINER:
-- - dono da função precisa ter privilegio de DDL.
-- - SECURITY DEFINER faz a função rodar com o privilégio do dono, não do caller.

-- Em ambiente Docker dev, o owner natural é o postgres superuser ou
-- isp_migrator (que tem CREATE no schema).


ALTER FUNCTION create_optical_reading_partition(DATE) OWNER TO isp_migrator;
ALTER FUNCTION create_optical_reading_partition(DATE) SECURITY DEFINER;

-- Nova função para drop seguro de partição especifica.
-- Recebe o NOME da partição (TEXT) ao invés de DATE para a task poder
-- iterar pg_inherits e passar o nome direto.
-- Valida o nome contra um padrão para impedir SQL injection caso
-- algum dia o caller seja menos confiável: aceita apenas o prefixo
-- 'optical_reading_' seguido de YYYY_MM.

CREATE OR REPLACE FUNCTION drop_optical_reading_partition(part_name TEXT)
RETURNS BOOLEAN AS $$
DECLARE
    safe_pattern TEXT := '^optical_reading_[0-9]{4}_[0-9]{2}$';
BEGIN
    IF part_name !~ safe_pattern THEN
        RAISE EXCEPTION 'nome de partição invalido: %', part_name;
    END IF;
    -- A partição default (optical_reading_default) NUNCA cai aqui por
    -- causa do regex (faltam dígitos de ano/mes).
    EXECUTE format('DROP TABLE IF EXISTS %I', part_name);
    RETURN TRUE;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

ALTER FUNCTION drop_optical_reading_partition(TEXT) OWNER TO isp_migrator;

-- GRANT EXECUTE para isp_app, que e quem chama do worker Celery.
GRANT EXECUTE ON FUNCTION create_optical_reading_partition(DATE) TO isp_app;
GRANT EXECUTE ON FUNCTION drop_optical_reading_partition(TEXT) TO isp_app;

COMMENT ON FUNCTION drop_optical_reading_partition(TEXT) IS
    'Drop seguro de partição mensal de optical_reading. Validador de nome '
    'recusa qualquer entrada fora do padrão optical_reading_YYYY_MM. '
    'SECURITY DEFINER permite que isp_app dispare DROP sem ter privilegio '
    'DDL direto no schema.';
