-- Initialize IoT Platform Database

-- Create databases
CREATE DATABASE device_registry;
CREATE DATABASE user_management;

-- Create users for application services
CREATE USER device_registry_user WITH PASSWORD 'device_registry_password';
CREATE USER data_ingestion_user WITH PASSWORD 'data_ingestion_password';
CREATE USER alert_engine_user WITH PASSWORD 'alert_engine_password';

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE device_registry TO device_registry_user;
GRANT ALL PRIVILEGES ON DATABASE device_registry TO data_ingestion_user;
GRANT ALL PRIVILEGES ON DATABASE device_registry TO alert_engine_user;

-- Switch to device_registry database
\c device_registry;

-- Create schema for device registry
CREATE SCHEMA IF NOT EXISTS devices;

-- Grant schema usage
GRANT ALL ON SCHEMA devices TO device_registry_user;
GRANT ALL ON SCHEMA devices TO data_ingestion_user;
GRANT ALL ON SCHEMA devices TO alert_engine_user;

-- Create extensions for device registry
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Create initial tables (will be handled by Alembic migrations)
-- This is just to ensure the database is properly initialized

-- Log initialization
INSERT INTO devices.device (device_id, name, device_type, status, owner_id, api_key)
VALUES (
    'init-device',
    'Initialization Device',
    'gateway',
    'inactive',
    'system',
    'init-api-key'
) ON CONFLICT (device_id) DO NOTHING;

-- Create initial indexes (will be handled by migrations)
-- This is just placeholder

COMMIT;

-- Display initialization complete
SELECT 'Database initialization complete' as status;