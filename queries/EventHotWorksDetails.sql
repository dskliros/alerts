SELECT
	e.id,
	e.name AS event_name,
	e.created_at,
	--et.name AS event_type,
    --ed.status_id AS status_id,
    es.name AS status
    --es.progress as progress
FROM 
	events e
LEFT JOIN event_types et ON e.type_id = et.id
LEFT JOIN vessels v ON e.vessel_id = v.id
LEFT JOIN vessel_subtypes vs ON v.subtype_id = vs.id
LEFT JOIN event_details ed ON ed.event_id = e.id
LEFT JOIN event_statuses es ON es.id = ed.status_id
WHERE
	e.type_id = :type_id
    AND es.id = :status_id
	AND LOWER(e.name) LIKE :name_filter
    AND LOWER(e.name) NOT LIKE :name_excluded
	AND e.created_at >= NOW() - INTERVAL '1 day' * :lookback_days
ORDER BY
	created_at ASC;
