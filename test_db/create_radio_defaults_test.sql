-- SQL script to create a test database with DMR radio default keys
-- This simulates encrypted frames from multiple DMR radios with default keys
-- Using realistic Message Indicator (MI) values that differ from the keys

DROP TABLE IF EXISTS radio_defaults_info;
CREATE TABLE radio_defaults_info (
    id INTEGER PRIMARY KEY,
    key_hex TEXT,
    key_block INTEGER,
    mi_hex TEXT,
    radio_type TEXT,
    description TEXT
);

-- Insert information about various radio default keys
-- Using realistic MI values (different from keys)
INSERT INTO radio_defaults_info (key_hex, key_block, mi_hex, radio_type, description) VALUES
    ('00000001', 1, '12AB34CD', 'Motorola/Generic', 'DMR Channel 1 default key'),
    ('00000005', 5, '98765432', 'Motorola/Generic', 'DMR Channel 5 default key'),
    ('0000000A', 10, 'A1B2C3D4', 'Motorola/Generic', 'DMR Channel 10 default key'),
    ('00000010', 16, 'FFDDEE22', 'Motorola/Generic', 'DMR Channel 16 default key'),
    ('0000001F', 31, '87654321', 'Motorola/Generic', 'DMR Channel 31 default key'),
    ('00000032', 50, 'ABCDEF12', 'Motorola/Generic', 'DMR Channel 50 default key'),
    ('00000042', 66, '55AABB33', 'Motorola XPR', 'XPR Series Channel 66 default key'),
    ('00000064', 100, '99887766', 'Motorola/Generic', 'DMR Channel 100 default key');

-- Create tables for each key with frames encrypted by that key
-- Each key gets its own table with the naming pattern C_[KEY_HEX]_S0
-- This matches the pattern used in the real database

-- Simulated frames encrypted with key 00000001 (Channel 1)
DROP TABLE IF EXISTS C_00000001_S0;
CREATE TABLE C_00000001_S0 (
    id INTEGER PRIMARY KEY,
    ambe_hex TEXT,
    timestamp TEXT,
    stream_id INTEGER,
    encrypted INTEGER,
    mi_present INTEGER,
    radio_id INTEGER
);

-- Insert frames encrypted with key 00000001
-- First byte of first frame "leaks" the block byte (01)
INSERT INTO C_00000001_S0 (ambe_hex, timestamp, stream_id, encrypted, mi_present, radio_id) VALUES
    ('0105077400004000', '2025-05-20 10:00:00', 12345, 1, 1, 1001),
    ('ED2D4F7100006000', '2025-05-20 10:00:01', 12345, 1, 1, 1001),
    ('596AF1C800008000', '2025-05-20 10:00:02', 12345, 1, 1, 1001);

-- Simulated frames encrypted with key 00000005 (Channel 5)
DROP TABLE IF EXISTS C_00000005_S0;
CREATE TABLE C_00000005_S0 (
    id INTEGER PRIMARY KEY,
    ambe_hex TEXT,
    timestamp TEXT,
    stream_id INTEGER,
    encrypted INTEGER,
    mi_present INTEGER,
    radio_id INTEGER
);

-- Insert frames encrypted with key 00000005
INSERT INTO C_00000005_S0 (ambe_hex, timestamp, stream_id, encrypted, mi_present, radio_id) VALUES
    ('0505077400004000', '2025-05-20 10:05:00', 12346, 1, 1, 1002),
    ('ED2D4F7100006000', '2025-05-20 10:05:01', 12346, 1, 1, 1002),
    ('596AF1C800008000', '2025-05-20 10:05:02', 12346, 1, 1, 1002);

-- Simulated frames encrypted with key 0000000A (Channel 10)
DROP TABLE IF EXISTS C_0000000A_S0;
CREATE TABLE C_0000000A_S0 (
    id INTEGER PRIMARY KEY,
    ambe_hex TEXT,
    timestamp TEXT,
    stream_id INTEGER,
    encrypted INTEGER,
    mi_present INTEGER,
    radio_id INTEGER
);

-- Insert frames encrypted with key 0000000A
INSERT INTO C_0000000A_S0 (ambe_hex, timestamp, stream_id, encrypted, mi_present, radio_id) VALUES
    ('0A05077400004000', '2025-05-20 10:10:00', 12347, 1, 1, 1003),
    ('ED2D4F7100006000', '2025-05-20 10:10:01', 12347, 1, 1, 1003),
    ('596AF1C800008000', '2025-05-20 10:10:02', 12347, 1, 1, 1003);

-- Simulated frames encrypted with key 00000010 (Channel 16)
DROP TABLE IF EXISTS C_00000010_S0;
CREATE TABLE C_00000010_S0 (
    id INTEGER PRIMARY KEY,
    ambe_hex TEXT,
    timestamp TEXT,
    stream_id INTEGER,
    encrypted INTEGER,
    mi_present INTEGER,
    radio_id INTEGER
);

-- Insert frames encrypted with key 00000010
INSERT INTO C_00000010_S0 (ambe_hex, timestamp, stream_id, encrypted, mi_present, radio_id) VALUES
    ('1005077400004000', '2025-05-20 10:16:00', 12348, 1, 1, 1004),
    ('ED2D4F7100006000', '2025-05-20 10:16:01', 12348, 1, 1, 1004),
    ('596AF1C800008000', '2025-05-20 10:16:02', 12348, 1, 1, 1004);

-- Simulated frames encrypted with key 0000001F (Channel 31)
DROP TABLE IF EXISTS C_0000001F_S0;
CREATE TABLE C_0000001F_S0 (
    id INTEGER PRIMARY KEY,
    ambe_hex TEXT,
    timestamp TEXT,
    stream_id INTEGER,
    encrypted INTEGER,
    mi_present INTEGER,
    radio_id INTEGER
);

-- Insert frames encrypted with key 0000001F
INSERT INTO C_0000001F_S0 (ambe_hex, timestamp, stream_id, encrypted, mi_present, radio_id) VALUES
    ('1F05077400004000', '2025-05-20 10:31:00', 12349, 1, 1, 1005),
    ('ED2D4F7100006000', '2025-05-20 10:31:01', 12349, 1, 1, 1005),
    ('596AF1C800008000', '2025-05-20 10:31:02', 12349, 1, 1, 1005);

-- Simulated frames encrypted with key 00000032 (Channel 50)
DROP TABLE IF EXISTS C_00000032_S0;
CREATE TABLE C_00000032_S0 (
    id INTEGER PRIMARY KEY,
    ambe_hex TEXT,
    timestamp TEXT,
    stream_id INTEGER,
    encrypted INTEGER,
    mi_present INTEGER,
    radio_id INTEGER
);

-- Insert frames encrypted with key 00000032
INSERT INTO C_00000032_S0 (ambe_hex, timestamp, stream_id, encrypted, mi_present, radio_id) VALUES
    ('3205077400004000', '2025-05-20 10:50:00', 12350, 1, 1, 1006),
    ('ED2D4F7100006000', '2025-05-20 10:50:01', 12350, 1, 1, 1006),
    ('596AF1C800008000', '2025-05-20 10:50:02', 12350, 1, 1, 1006);

-- Simulated frames encrypted with key 00000042 (Channel 66)
DROP TABLE IF EXISTS C_00000042_S0;
CREATE TABLE C_00000042_S0 (
    id INTEGER PRIMARY KEY,
    ambe_hex TEXT,
    timestamp TEXT,
    stream_id INTEGER,
    encrypted INTEGER,
    mi_present INTEGER,
    radio_id INTEGER
);

-- Insert frames encrypted with key 00000042
INSERT INTO C_00000042_S0 (ambe_hex, timestamp, stream_id, encrypted, mi_present, radio_id) VALUES
    ('4205077400004000', '2025-05-20 11:06:00', 12351, 1, 1, 1007),
    ('ED2D4F7100006000', '2025-05-20 11:06:01', 12351, 1, 1, 1007),
    ('596AF1C800008000', '2025-05-20 11:06:02', 12351, 1, 1, 1007);

-- Simulated frames encrypted with key 00000064 (Channel 100)
DROP TABLE IF EXISTS C_00000064_S0;
CREATE TABLE C_00000064_S0 (
    id INTEGER PRIMARY KEY,
    ambe_hex TEXT,
    timestamp TEXT,
    stream_id INTEGER,
    encrypted INTEGER,
    mi_present INTEGER,
    radio_id INTEGER
);

-- Insert frames encrypted with key 00000064
INSERT INTO C_00000064_S0 (ambe_hex, timestamp, stream_id, encrypted, mi_present, radio_id) VALUES
    ('6405077400004000', '2025-05-20 12:00:00', 12352, 1, 1, 1008),
    ('ED2D4F7100006000', '2025-05-20 12:00:01', 12352, 1, 1, 1008),
    ('596AF1C800008000', '2025-05-20 12:00:02', 12352, 1, 1, 1008);

-- Create a table for 18 AMBE frames test data (spanning 3 superframes)
DROP TABLE IF EXISTS C_ABCDEF78_S0;
CREATE TABLE C_ABCDEF78_S0 (
    id INTEGER PRIMARY KEY,
    ambe_hex TEXT,
    timestamp TEXT,
    stream_id INTEGER,
    encrypted INTEGER,
    mi_present INTEGER,
    radio_id INTEGER
);

-- Insert 18 AMBE frames encrypted with key ABCDEF78 (spanning 3 superframes)
INSERT INTO C_ABCDEF78_S0 (ambe_hex, timestamp, stream_id, encrypted, mi_present, radio_id) VALUES
    ('7805077400004000', '2025-05-20 14:00:00', 12360, 1, 1, 1010),
    ('ED2D4F7100006000', '2025-05-20 14:00:01', 12360, 1, 1, 1010),
    ('596AF1C800008000', '2025-05-20 14:00:02', 12360, 1, 1, 1010),
    ('A104B23100001000', '2025-05-20 14:00:03', 12360, 1, 1, 1010),
    ('F392A45600002000', '2025-05-20 14:00:04', 12360, 1, 1, 1010),
    ('C823D67800003000', '2025-05-20 14:00:05', 12360, 1, 1, 1010),
    ('3B561A9000004000', '2025-05-20 14:00:06', 12360, 1, 1, 1010),
    ('D49F2E1200005000', '2025-05-20 14:00:07', 12360, 1, 1, 1010),
    ('9A37C56700006000', '2025-05-20 14:00:08', 12360, 1, 1, 1010),
    ('4E70F89A00007000', '2025-05-20 14:00:09', 12360, 1, 1, 1010),
    ('B2C5D34500008000', '2025-05-20 14:00:10', 12360, 1, 1, 1010),
    ('2871E69B00009000', '2025-05-20 14:00:11', 12360, 1, 1, 1010),
    ('7F39AD4C0000A000', '2025-05-20 14:00:12', 12360, 1, 1, 1010),
    ('E5C12F670000B000', '2025-05-20 14:00:13', 12360, 1, 1, 1010),
    ('0A73B8900000C000', '2025-05-20 14:00:14', 12360, 1, 1, 1010),
    ('5946CD120000D000', '2025-05-20 14:00:15', 12360, 1, 1, 1010),
    ('C08F315E0000E000', '2025-05-20 14:00:16', 12360, 1, 1, 1010),
    ('86D7492A0000F000', '2025-05-20 14:00:17', 12360, 1, 1, 1010);

-- Create a metadata table to store test database information
DROP TABLE IF EXISTS test_metadata;
CREATE TABLE test_metadata (
    id INTEGER PRIMARY KEY,
    created_at TEXT,
    description TEXT
);

INSERT INTO test_metadata (created_at, description) VALUES
    (datetime('now'), 'DMR Radio Default Keys Test Database - Created for testing the --radio-defaults and --optimal-frames optimizations');