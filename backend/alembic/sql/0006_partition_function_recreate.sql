-- Migration 0006: recria create_optical_reading_partition com cabeçalho
-- SECURITY DEFINER + SET search_path. A 0005 fez ALTER FUNCTION post-hoc;
-- a forma canônica e declarativa do PostgreSQL recomenda colocar essas
-- propriedades no CREATE OR REPLACE. Há três diferenças práticas:

-- 1. SET search_path = public, pg_temp blinda a função contra hijacking
--    de schema. Sem isso, search_path do session influência onde a
--    função resolve nomes (incluindo a tabela pai optical_reading), o
--    que pode levar a falhas confusas e e considerado anti-pattern
--    em SECURITY DEFINER.
--
-- 2. Garante GRANT CREATE em public para isp_migrator.
--
-- 3. Reaplica SECURITY DEFINER + OWNER no header CREATE OR REPLACE,
--    eliminando dependência de ALTER posterior.
--
-- Mesma cobertura para drop_optical_reading_partition.

-- 1) GRANT CREATE defensivo no schema public.
-- isp_migrator JÁ criou todas as tabelas na 0001, então deve ter CREATE.
-- Idempotente: GRANT já existente não falha.
GRANT CREATE ON SCHEMA public TO isp_migrator;

-- 2) Recria create_optical_reading_partition com cabeçalho completo.
-- Body idêntico ao da 0001; muda apenas a declaração da função.
CREATE OR REPLACE FUNCTION create_optical_reading_partition(target_month DATE)
RETURNS TEXT
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    part_name   TEXT;
    range_start TEXT;
    range_end   TEXT;
    month_start DATE;
BEGIN
    month_start := date_trunc('month', target_month)::date;
    part_name   := 'optical_reading_' || to_char(month_start, 'YYYY_MM');
    range_start := to_char(month_start, 'YYYY-MM-DD');
    range_end   := to_char(month_start + INTERVAL '1 month', 'YYYY-MM-DD');

    EXECUTE format(
        'CREATE TABLE IF NOT EXISTS %I PARTITION OF optical_reading
        FOR VALUES FROM (%L) TO (%L)',
        part_name, range_start, range_end
    );

    RETURN part_name;
END;
$$;

ALTER FUNCTION create_optical_reading_partition(DATE) OWNER TO isp_migrator;
GRANT EXECUTE ON FUNCTION create_optical_reading_partition(DATE) TO isp_app;

-- 3) Aplica SET search_path em drop_optical_reading_partition (criada na 0005).
-- ALTER FUNCTION para adicionar setting sem mudar o corpo.
ALTER FUNCTION drop_optical_reading_partition(TEXT) SET search_path = public, pg_temp;

-- Mensagens de comentário atualizadas
COMMENT ON FUNCTION create_optical_reading_partition(DATE) IS
    'Cria partição mensal de optical_reading. SECURITY DEFINER + search_path '
    'fixo em public permite que isp_app invoque sem ter privilegio DDL direto. '
    'Chamar mensalmente via app.tasks.partitions.ensure_optical_partitions.';
