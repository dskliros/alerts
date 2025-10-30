SELECT
	e.id,
	e.name AS event_name,
	e.created_at,
	et.name AS event_type
FROM 
	events e
LEFT JOIN event_types et ON e.type_id = et.id
LEFT JOIN vessels v ON e.vessel_id = v.id
LEFT JOIN vessel_subtypes vs ON v.subtype_id = vs.id
WHERE
	e.type_id = :type_id --18
	AND LOWER(e.name) LIKE :name_filter --'%hot%'
    AND LOWER(e.name) NOT LIKE :name_excluded
	AND e.created_at >= NOW() - INTERVAL '1 day' * :lookback_days --'140 days'
ORDER BY
	created_at ASC;
