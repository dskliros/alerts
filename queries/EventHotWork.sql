SELECT 
    id,
    name AS event_name,
    created_at
FROM 
    events
WHERE
    type_id = :type_id
    AND LOWER(name) LIKE :name_filter
    AND created_at >= NOW() - INTERVAL '1 day' * :lookback_days
ORDER BY 
    created_at DESC
