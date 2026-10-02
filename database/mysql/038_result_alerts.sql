-- Results-published alerts to parents.
ALTER TABLE parent_alerts DROP CONSTRAINT chk_parent_alerts_kind;
ALTER TABLE parent_alerts ADD CONSTRAINT chk_parent_alerts_kind CHECK (kind IN ('absence', 'remark', 'fee', 'result'));
