SELECT
    e.id,
    et.name
FROM
    event_types et
LEFT JOIN events e ON et.id = :type_id
WHERE
    et.id = :type_id;
