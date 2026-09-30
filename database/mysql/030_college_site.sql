-- 030: college details for the public website: year established, accreditation
-- line (e.g. "NAAC A+ | AICTE approved | Affiliated to JNTUA"), highlight
-- figures, programs offered, and the principal's message.
-- highlights: JSON list of {"value": "25+", "label": "Years of excellence"}.
-- programs: JSON list of {"name", "level", "duration", "seats", "description"}.
-- Applied automatically by the backend.

ALTER TABLE school_sites ADD COLUMN established VARCHAR(10) NOT NULL DEFAULT '';
ALTER TABLE school_sites ADD COLUMN accreditation VARCHAR(300) NOT NULL DEFAULT '';
ALTER TABLE school_sites ADD COLUMN highlights LONGTEXT NULL;
ALTER TABLE school_sites ADD COLUMN programs LONGTEXT NULL;
ALTER TABLE school_sites ADD COLUMN principal_name VARCHAR(150) NOT NULL DEFAULT '';
ALTER TABLE school_sites ADD COLUMN principal_title VARCHAR(100) NOT NULL DEFAULT '';
ALTER TABLE school_sites ADD COLUMN principal_message TEXT NULL;

