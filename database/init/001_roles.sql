-- TelemetryScope Database Initialization
-- Script: 001_roles.sql
-- Purpose: Create roles needed for telemetryscope application

CREATE ROLE telemetryscope_writer WITH LOGIN PASSWORD 'writer_password';
CREATE ROLE telemetryscope_reader WITH LOGIN PASSWORD 'reader_password';
CREATE ROLE telemetryscope_migrator WITH LOGIN PASSWORD 'migrator_password';
