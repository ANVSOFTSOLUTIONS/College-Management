-- 031: five college website templates join the ten existing ones.
-- Applied automatically by the backend.

ALTER TABLE schools DROP CONSTRAINT chk_schools_template;
ALTER TABLE schools ADD CONSTRAINT chk_schools_template CHECK (template IN (
    'classic', 'modern', 'vibrant', 'emerald', 'royal', 'neon', 'sunrise', 'ocean', 'editorial', 'split',
    'university', 'engineering', 'medical', 'business', 'arts'
));
