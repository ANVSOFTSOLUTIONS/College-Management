-- 016: module switches are now enforced. Homework and ID cards/certificates
-- were added after schools chose their modules, so switch them on for every
-- existing school (nothing was enforced before, so they were already in use).
-- Applied automatically by the backend.

UPDATE schools SET enabled_modules = JSON_ARRAY_APPEND(enabled_modules, '$', 'homework')
WHERE NOT JSON_CONTAINS(enabled_modules, '"homework"');

UPDATE schools SET enabled_modules = JSON_ARRAY_APPEND(enabled_modules, '$', 'certificates')
WHERE NOT JSON_CONTAINS(enabled_modules, '"certificates"');
