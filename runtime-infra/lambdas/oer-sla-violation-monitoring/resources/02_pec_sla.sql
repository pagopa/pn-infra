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
send_digital_source AS (
    SELECT
        t.iun,
        t.timelineElementId,
        CAST(regexp_extract(t.timelineElementId, 'ATTEMPT_(\d+)', 1) AS INTEGER) AS attempt,
        CAST(regexp_extract(t.timelineElementId, 'RECINDEX_(\d+)', 1) AS INTEGER) AS recindex,
        concat(t.p_year, t.p_month, t.p_day, t.p_hour) AS partition_key,
        from_iso8601_timestamp(t.timestamp) AS ts_event
    FROM pn_timelines_json_view t
    WHERE t.category = 'SEND_DIGITAL_DOMICILE'
),

-- Normalizzazione sorgente OUTCOMES: calcolo una sola volta partizione e timestamp
outcome_source AS (
    SELECT
        t.iun,
        t.timelineElementId,
        CAST(regexp_extract(t.timelineElementId, 'ATTEMPT_(\d+)', 1) AS INTEGER) AS attempt,
        CAST(regexp_extract(t.timelineElementId, 'RECINDEX_(\d+)', 1) AS INTEGER) AS recindex,
        t.category,
        concat(t.p_year, t.p_month, t.p_day, t.p_hour) AS partition_key,
        from_iso8601_timestamp(t.timestamp) AS ts_event
    FROM pn_timelines_json_view t
    WHERE t.category = 'SEND_DIGITAL_FEEDBACK'
),

-- FASE 1: Richieste di VALIDATE nell'intervallo [start_time, validate_end_time)
send_digital AS (
    SELECT 
        v.iun,
        v.timelineElementId,
        v.ts_event AS ts_validate,
        v.attempt,
        v.recindex
    FROM send_digital_source v
    CROSS JOIN date_context dc
    WHERE v.partition_key >= date_format(dc.start_time, '%Y%m%d%H')
      AND v.partition_key <= date_format(dc.validate_end_time - INTERVAL '1' SECOND, '%Y%m%d%H')
      AND v.ts_event >= dc.start_time
      AND v.ts_event < dc.validate_end_time 
),

-- FASE 2: Esiti cercati fino al momento attuale dell'esecuzione [start_time, outcome_end_time]
outcomes AS (
    SELECT 
        o.iun,
        o.attempt,
        o.recindex,
        1 AS ha_digital_feedback,
        MAX(o.ts_event) AS ts_outcome
    FROM outcome_source o
    CROSS JOIN date_context dc
    WHERE o.partition_key >= date_format(dc.start_time, '%Y%m%d%H')
      AND o.partition_key <= date_format(dc.outcome_end_time, '%Y%m%d%H')
      AND o.ts_event >= dc.start_time
      AND o.ts_event <= dc.outcome_end_time
    GROUP BY o.iun,
             o.attempt,
             o.recindex
)

-- FASE 3: Isolamento dei VALIDATE dell'ora precedente senza esito
SELECT 
    v.iun,
    v.timelineElementId,
    1 AS ha_validate_request,
    COALESCE(o.ha_digital_feedback, 0) AS ha_digital_feedback,
    v.ts_validate,
    o.ts_outcome,
    date_diff('hour', v.ts_validate, current_timestamp) AS diff_hour
FROM send_digital v
LEFT JOIN outcomes o 
       ON v.iun = o.iun 
      AND v.recindex = o.recindex 
      AND v.attempt = o.attempt
WHERE o.iun IS NULL;