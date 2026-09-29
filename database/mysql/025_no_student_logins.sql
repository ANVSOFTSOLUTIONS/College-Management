-- 025: students no longer sign in. Parents use the parent login for
-- everything (results, fees, documents, leave). Existing student accounts
-- are switched off, which also ends any signed-in student session. The rows
-- are kept (not deleted) so past records that point at them stay intact.
-- Applied automatically by the backend.

UPDATE users SET status = 'inactive' WHERE role = 'student' AND status = 'active';
