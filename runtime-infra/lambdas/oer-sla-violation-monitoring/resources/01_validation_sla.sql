WITH date_context AS (
    SELECT 
        -- 1. START_TIME: Fornito dall'esterno (es. '2026-08-11T07:00:00Z')
        from_iso8601_timestamp('2026-08-11T07:00:00Z') AS start_time,
        
        -- 2. END_TIME VALIDATE: Fine esatta dell'ora precedente (es. 09:00:00)
        date_trunc('hour', current_timestamp) AS validate_end_time,
        
        -- 3. END_TIME OUTCOMES: Ora attuale di esecuzione della query (es. 09:15:00)
        current_timestamp AS outcome_end_time
),

-- FASE 1: Richieste di VALIDATE nell'intervallo [start_time, validate_end_time)
validates AS (
    SELECT 
        t.iun,
        from_iso8601_timestamp(t.timestamp) AS ts_validate
    FROM pn_timelines_json_view t
    CROSS JOIN date_context dc
    WHERE t.category = 'VALIDATE_NORMALIZE_ADDRESSES_REQUEST'
      
      -- Filtro partizioni: dalle start_time fino all'ora precedente inclusa
      AND concat(t.p_year, t.p_month, t.p_day, t.p_hour) >= date_format(dc.start_time, '%Y%m%d%H')
      AND concat(t.p_year, t.p_month, t.p_day, t.p_hour) <= date_format(dc.validate_end_time - INTERVAL '1' SECOND, '%Y%m%d%H')
      
      -- Filtro temporale puntuale: stretto prima delle 09:00:00
      AND from_iso8601_timestamp(t.timestamp) >= dc.start_time
      AND from_iso8601_timestamp(t.timestamp) < dc.validate_end_time
),

-- FASE 2: Esiti cercati fino al momento attuale dell'esecuzione [start_time, outcome_end_time]
outcomes AS (
    SELECT 
        t.iun,
        MAX(CASE WHEN t.category = 'REQUEST_ACCEPTED' THEN 1 ELSE 0 END) AS ha_request_accepted,
        MAX(CASE WHEN t.category = 'REQUEST_REFUSED' THEN 1 ELSE 0 END) AS ha_request_refused,
        MAX(from_iso8601_timestamp(t.timestamp)) AS ts_outcome
    FROM pn_timelines_json_view t
    CROSS JOIN date_context dc
    WHERE t.category IN ('REQUEST_ACCEPTED', 'REQUEST_REFUSED')
      
      -- Filtro partizioni: dall'ora di inizio fino all'ora corrente dell'esecuzione
      AND concat(t.p_year, t.p_month, t.p_day, t.p_hour) >= date_format(dc.start_time, '%Y%m%d%H')
      AND concat(t.p_year, t.p_month, t.p_day, t.p_hour) <= date_format(dc.outcome_end_time, '%Y%m%d%H')
      
      -- Filtro temporale puntuale sui timestamp reali
      AND from_iso8601_timestamp(t.timestamp) >= dc.start_time
      AND from_iso8601_timestamp(t.timestamp) <= dc.outcome_end_time
    GROUP BY t.iun
)

-- FASE 3: Isolamento dei VALIDATE dell'ora precedente senza esito
SELECT 
    v.iun,
    1 AS ha_validate_request,
    COALESCE(o.ha_request_accepted, 0) AS ha_request_accepted,
    COALESCE(o.ha_request_refused, 0) AS ha_request_refused,
    v.ts_validate,
    o.ts_outcome,
    date_diff('second', v.ts_validate, o.ts_outcome) AS diff_seconds
FROM validates v
LEFT JOIN outcomes o ON v.iun = o.iun
WHERE o.iun IS NULL;