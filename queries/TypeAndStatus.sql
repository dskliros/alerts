SELECT
    et.name AS type_name,
    es.name AS status_name
FROM
    events e
LEFT JOIN event_types et ON e.type_id = et.id
LEFT JOIN event_details ed ON ed.event_id = e.id
LEFT JOIN event_statuses es ON es.id = ed.status_id
WHERE 
    e.type_id = :type_id
    AND es.id = :status_id;
