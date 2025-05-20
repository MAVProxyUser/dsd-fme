#!/bin/bash

# Script to create the radio defaults test database

DB_FILE="radio_defaults_test.db"
SQL_FILE="create_radio_defaults_test.sql"
DB_PATH="test_db/${DB_FILE}"
SQL_PATH="test_db/${SQL_FILE}"

echo "Creating test database: ${DB_FILE}"

# Remove existing database
if [ -f "$DB_PATH" ]; then
    rm "$DB_PATH"
    echo "Removed existing database."
fi

# Create a new database
sqlite3 "$DB_PATH" "CREATE TABLE test(id INTEGER PRIMARY KEY);"
echo "Database initialized."

# Load the SQL script
echo "Executing SQL script: ${SQL_FILE}"
sqlite3 "$DB_PATH" < "$SQL_PATH"

# Verify tables created
echo "Verifying database tables:"
sqlite3 "$DB_PATH" "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;"

# Verify radio_defaults_info table
echo "Checking radio_defaults_info table:"
sqlite3 "$DB_PATH" "SELECT key_hex, key_block, radio_type FROM radio_defaults_info ORDER BY key_block;"

# Verify number of frames in each table
echo "Checking frame counts in each table:"
for TABLE in $(sqlite3 "$DB_PATH" "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'C_%_S0' ORDER BY name;"); do
    COUNT=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM $TABLE;")
    echo "$TABLE: $COUNT frames"
done

echo "Database creation completed."