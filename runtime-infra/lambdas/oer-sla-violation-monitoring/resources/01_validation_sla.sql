WITH date_context AS (
    SELECT 
        -- 1. START_TIME: Fornito dall'esterno (es. '2026-08-11T07:00:00Z')
        from_iso8601_timestamp('<START_TIME>') AS start_time,
        
        -- 2. END_TIME VALIDATE: Fine esatta dell'ora precedente (es. 09:00:00)
        date_trunc('hour', current_timestamp) AS validate_end_time,
        
        -- 3. END_TIME OUTCOMES: Ora attuale di esecuzione della query (es. 09:15:00)
        current_timestamp AS outcome_end_time
),

-- Normalizzazione sorgente VALIDATE: calcolo una sola volta partizione e timestamp
validate_source AS (
    SELECT
        t.iun,
        concat(t.p_year, t.p_month, t.p_day, t.p_hour) AS partition_key,
        from_iso8601_timestamp(t.timestamp) AS ts_event
    FROM pn_timelines_json_view t
    WHERE t.category = 'VALIDATE_NORMALIZE_ADDRESSES_REQUEST'
),

-- Normalizzazione sorgente OUTCOMES: calcolo una sola volta partizione e timestamp
outcome_source AS (
    SELECT
        t.iun,
        t.category,
        concat(t.p_year, t.p_month, t.p_day, t.p_hour) AS partition_key,
        from_iso8601_timestamp(t.timestamp) AS ts_event
    FROM pn_timelines_json_view t
    WHERE t.category IN ('REQUEST_ACCEPTED', 'REQUEST_REFUSED')
),

-- FASE 1: Richieste di VALIDATE nell'intervallo [start_time, validate_end_time)
validates AS (
    SELECT 
        v.iun,
        v.ts_event AS ts_validate
    FROM validate_source v
    CROSS JOIN date_context dc
    WHERE
      -- Filtro partizioni: dalle start_time fino all'ora precedente inclusa
      v.partition_key >= date_format(dc.start_time, '%Y%m%d%H')
      AND v.partition_key <= date_format(dc.validate_end_time - INTERVAL '1' SECOND, '%Y%m%d%H')
      
      -- Filtro temporale puntuale: stretto prima delle 09:00:00
      AND v.ts_event >= dc.start_time
      AND v.ts_event < dc.validate_end_time
),

-- FASE 2: Esiti cercati fino al momento attuale dell'esecuzione [start_time, outcome_end_time]
outcomes AS (
    SELECT 
        o.iun,
        MAX(CASE WHEN o.category = 'REQUEST_ACCEPTED' THEN 1 ELSE 0 END) AS ha_request_accepted,
        MAX(CASE WHEN o.category = 'REQUEST_REFUSED' THEN 1 ELSE 0 END) AS ha_request_refused,
        MAX(o.ts_event) AS ts_outcome
    FROM outcome_source o
    CROSS JOIN date_context dc
    WHERE
      -- Filtro partizioni: dall'ora di inizio fino all'ora corrente dell'esecuzione
      o.partition_key >= date_format(dc.start_time, '%Y%m%d%H')
      AND o.partition_key <= date_format(dc.outcome_end_time, '%Y%m%d%H')
      
      -- Filtro temporale puntuale sui timestamp reali
      AND o.ts_event >= dc.start_time
      AND o.ts_event <= dc.outcome_end_time
    GROUP BY o.iun
)

-- FASE 3: Isolamento dei VALIDATE dell'ora precedente senza esito
SELECT 
    v.iun,
    1 AS ha_validate_request,
    COALESCE(o.ha_request_accepted, 0) AS ha_request_accepted,
    COALESCE(o.ha_request_refused, 0) AS ha_request_refused,
    v.ts_validate,
    o.ts_outcome,
    date_diff('hour', v.ts_validate, current_timestamp) AS diff_hour
FROM validates v
LEFT JOIN outcomes o ON v.iun = o.iun
WHERE o.iun IS NULL;