-- CaseDesk Database Size Report
-- Run: mysql -u root -p < check_db_size.sql

USE updated_casedesk;

SELECT '=== TABLE SIZES ===' AS '';

SELECT 
    table_name AS 'Table',
    ROUND(data_length / 1024 / 1024, 2) AS 'Data (MB)',
    ROUND(index_length / 1024 / 1024, 2) AS 'Index (MB)',
    ROUND((data_length + index_length) / 1024 / 1024, 2) AS 'Total (MB)',
    table_rows AS 'Rows'
FROM information_schema.tables 
WHERE table_schema = 'updated_casedesk'
ORDER BY (data_length + index_length) DESC;

SELECT '=== TOTAL DATABASE SIZE ===' AS '';

SELECT 
    ROUND(SUM(data_length) / 1024 / 1024, 2) AS 'Total Data (MB)',
    ROUND(SUM(index_length) / 1024 / 1024, 2) AS 'Total Index (MB)',
    ROUND(SUM(data_length + index_length) / 1024 / 1024, 2) AS 'Grand Total (MB)',
    ROUND(SUM(data_length + index_length) / 1024 / 1024 / 1024, 3) AS 'Grand Total (GB)'
FROM information_schema.tables 
WHERE table_schema = 'updated_casedesk';

SELECT '=== RAW TEXT SIZE (the biggest space consumer) ===' AS '';

SELECT 
    'cases.raw_text' AS 'Column',
    COUNT(*) AS 'Rows',
    ROUND(SUM(LENGTH(raw_text)) / 1024 / 1024, 2) AS 'Text Size (MB)',
    ROUND(AVG(LENGTH(raw_text)) / 1024, 2) AS 'Avg per Case (KB)'
FROM cases;

SELECT 
    'case_files.raw_text' AS 'Column',
    COUNT(*) AS 'Rows',
    ROUND(SUM(LENGTH(raw_text)) / 1024 / 1024, 2) AS 'Text Size (MB)',
    ROUND(AVG(LENGTH(raw_text)) / 1024, 2) AS 'Avg per File (KB)'
FROM case_files;

SELECT '=== PROJECTION FOR 10,000 CASES ===' AS '';

SELECT 
    ROUND(AVG(LENGTH(raw_text)) / 1024, 2) AS 'Avg Text per Case (KB)',
    ROUND(AVG(LENGTH(raw_text)) / 1024 * 10000 / 1024, 2) AS 'Projected 10K Cases (MB)',
    ROUND(AVG(LENGTH(raw_text)) / 1024 * 10000 / 1024 / 1024, 2) AS 'Projected 10K Cases (GB)'
FROM cases
WHERE raw_text IS NOT NULL AND LENGTH(raw_text) > 0;
