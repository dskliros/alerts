SELECT
	e.id,
	e.name AS event_name,
	e.created_at,
    es.name AS status,
    v.email AS email
    --v.id AS vessel_id,
    --v.name AS vessel_name
FROM 
	events e
LEFT JOIN vessels v ON v.id = e.vessel_id
--LEFT JOIN vessel_subtypes vs ON vs.id = v.subtype_id
LEFT JOIN event_details ed ON ed.event_id = e.id
LEFT JOIN event_statuses es ON es.id = ed.status_id
WHERE
	e.type_id = :type_id
    AND es.id = :status_id
	AND LOWER(e.name) LIKE :name_filter
    AND LOWER(e.name) NOT LIKE :name_excluded
	AND ed.synced_at >= NOW() - INTERVAL '1 day' * :lookback_days
ORDER BY
	ed.synced_at ASC;
