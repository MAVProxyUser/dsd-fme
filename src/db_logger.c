#include <stdio.h>
#include <stdint.h>
#include <sqlite3.h>
#include <time.h>
#include <sys/time.h>
#include <string.h>
#include <stdlib.h>
#include <unistd.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <libgen.h>
#include <errno.h>
#include "db_logger.h"

/* Global variables that can be accessed by other files */
sqlite3 *db = NULL;                         /* Single database handle for the entire application */
uint64_t current_h_mi = 0;
uint32_t current_c_mi = 0;
int current_superframe_id = 0;
uint32_t current_algid = 0;
static int current_context = 0;             /* 1 = header, 2 = control */
static int current_slot = 0;
static int frame_count_in_superframe = 0;
static char current_capture_session[64] = {0};
static char current_db_path[1024] = {0};    /* Increased buffer to prevent truncation */
static char master_db_path[1024] = {0};     /* Increased buffer to prevent truncation */
static char archive_dir[1024] = {0};        /* Increased buffer to prevent truncation */

/* Prepared statements for common operations */
static sqlite3_stmt *stmt_insert_superframe = NULL;
static sqlite3_stmt *stmt_update_superframe = NULL;
static sqlite3_stmt *stmt_insert_ambe = NULL;
static sqlite3_stmt *stmt_check_superframes = NULL;

/* LFSR functions for SQLite */
static void lfsr_next_mi_function(sqlite3_context *context, int argc, sqlite3_value **argv) {
    if (argc != 1) {
        sqlite3_result_error(context, "lfsr_next_mi requires exactly one argument", -1);
        return;
    }
    
    sqlite3_int64 current_mi = sqlite3_value_int64(argv[0]);
    
    /* LFSR implementation - the buggy one from DMR */
    uint32_t state = (uint32_t)current_mi;
    uint32_t bit = ((state >> 31) ^ (state >> 3) ^ (state >> 1)) & 0x1;
    uint32_t new_state = ((state << 1) | bit) & 0xFFFFFFFF;
    
    sqlite3_result_int64(context, (sqlite3_int64)new_state);
}

static void lfsr_32_steps_function(sqlite3_context *context, int argc, sqlite3_value **argv) {
    if (argc != 1) {
        sqlite3_result_error(context, "lfsr_32_steps requires exactly one argument", -1);
        return;
    }
    
    sqlite3_int64 current_mi = sqlite3_value_int64(argv[0]);
    uint32_t state = (uint32_t)current_mi;
    
    /* Apply 32 LFSR steps */
    for (int i = 0; i < 32; i++) {
        uint32_t bit = ((state >> 31) ^ (state >> 3) ^ (state >> 1)) & 0x1;
        state = ((state << 1) | bit) & 0xFFFFFFFF;
    }
    
    sqlite3_result_int64(context, (sqlite3_int64)state);
}

/* Fix existing superframes that might be encrypted but don't have the flag set */
void db_fix_encrypted_flags(void) {
    /* Do not call db_init() here to avoid circular dependency */
    if (!db) return;
    
    fprintf(stderr, "Starting to fix encrypted flags in database...\n");
    
    char *sql = 
        "UPDATE superframes SET encrypted = 1 "
        "WHERE encrypted = 0 AND (h_mi > 0 OR c_mi > 0 OR privacy_algid > 0)";
    
    char *errmsg = NULL;
    int rc = sqlite3_exec(db, sql, NULL, NULL, &errmsg);
    
    if (rc != SQLITE_OK) {
        fprintf(stderr, "Error updating encrypted flags: %s\n", errmsg);
        sqlite3_free(errmsg);
    } else {
        int rows_changed = sqlite3_changes(db);
        fprintf(stderr, "Updated encrypted flag for %d superframes\n", rows_changed);
        
        /* Also update the dmr_auto_correlations table with any missing entries */
        sql = 
            "INSERT OR IGNORE INTO dmr_auto_correlations "
            "(header_mi, content_mi, slot, algid, first_timestamp, last_timestamp, session_id) "
            "SELECT h_mi, c_mi, slot, privacy_algid, start_timestamp, start_timestamp, session_id "
            "FROM superframes "
            "WHERE (h_mi > 0 OR c_mi > 0 OR privacy_algid > 0) "
            "AND c_mi NOT IN (SELECT content_mi FROM dmr_auto_correlations)";
        
        rc = sqlite3_exec(db, sql, NULL, NULL, &errmsg);
        if (rc != SQLITE_OK) {
            fprintf(stderr, "Error inserting missing auto correlations: %s\n", errmsg);
            sqlite3_free(errmsg);
        } else {
            rows_changed = sqlite3_changes(db);
            fprintf(stderr, "Added %d missing entries to dmr_auto_correlations\n", rows_changed);
        }
    }
}

/* Register LFSR functions with SQLite */
void db_register_lfsr_functions(sqlite3 *db_conn) {
    int rc;
    
    /* Register with full persistence for all connections */
    rc = sqlite3_create_function_v2(
        db_conn,
        "lfsr_next_mi",
        1,
        SQLITE_UTF8 | SQLITE_DETERMINISTIC, /* Deterministic function for better caching */
        NULL,
        lfsr_next_mi_function,
        NULL,
        NULL,
        NULL  /* No destructor needed */
    );
    if (rc != SQLITE_OK) {
        fprintf(stderr, "Failed to register lfsr_next_mi function: %s\n", sqlite3_errmsg(db_conn));
    } else {
        fprintf(stderr, "Successfully registered lfsr_next_mi function\n");
    }
    
    /* Verify function was registered */
    sqlite3_stmt *stmt;
    rc = sqlite3_prepare_v2(db_conn, "SELECT lfsr_next_mi(12345)", -1, &stmt, NULL);
    if (rc != SQLITE_OK) {
        fprintf(stderr, "Error preparing lfsr_next_mi test: %s\n", sqlite3_errmsg(db_conn));
    } else {
        if (sqlite3_step(stmt) == SQLITE_ROW) {
            sqlite3_int64 result = sqlite3_column_int64(stmt, 0);
            fprintf(stderr, "lfsr_next_mi test successful: 12345 -> %lld\n", (long long)result);
        } else {
            fprintf(stderr, "lfsr_next_mi test failed to return a row\n");
        }
        sqlite3_finalize(stmt);
    }
    
    /* Register 32 steps function */
    rc = sqlite3_create_function_v2(
        db_conn,
        "lfsr_32_steps",
        1,
        SQLITE_UTF8 | SQLITE_DETERMINISTIC, /* Deterministic function for better caching */
        NULL,
        lfsr_32_steps_function,
        NULL,
        NULL,
        NULL  /* No destructor needed */
    );
    if (rc != SQLITE_OK) {
        fprintf(stderr, "Failed to register lfsr_32_steps function: %s\n", sqlite3_errmsg(db_conn));
    } else {
        fprintf(stderr, "Successfully registered lfsr_32_steps function\n");
    }
    
    /* Verify function was registered */
    rc = sqlite3_prepare_v2(db_conn, "SELECT lfsr_32_steps(12345)", -1, &stmt, NULL);
    if (rc != SQLITE_OK) {
        fprintf(stderr, "Error preparing lfsr_32_steps test: %s\n", sqlite3_errmsg(db_conn));
    } else {
        if (sqlite3_step(stmt) == SQLITE_ROW) {
            sqlite3_int64 result = sqlite3_column_int64(stmt, 0);
            fprintf(stderr, "lfsr_32_steps test successful: 12345 -> %lld\n", (long long)result);
        } else {
            fprintf(stderr, "lfsr_32_steps test failed to return a row\n");
        }
        sqlite3_finalize(stmt);
    }
    
    /* Create a special table with information about the LFSR functions */
    char *sql = sqlite3_mprintf(
        "CREATE TABLE IF NOT EXISTS lfsr_function_info ("
        "  id INTEGER PRIMARY KEY,"
        "  function_name TEXT,"
        "  description TEXT,"
        "  sample_input INTEGER,"
        "  sample_output INTEGER"
        ");"
        
        "INSERT OR REPLACE INTO lfsr_function_info (id, function_name, description, sample_input, sample_output) "
        "VALUES (1, 'lfsr_next_mi', 'Calculates next MI using x^32 + x^4 + x^2 + 1 polynomial', 12345, %lld);"
        
        "INSERT OR REPLACE INTO lfsr_function_info (id, function_name, description, sample_input, sample_output) "
        "VALUES (2, 'lfsr_32_steps', 'Calculates MI after 32 steps using x^32 + x^4 + x^2 + 1 polynomial', 12345, %lld);",
        (long long)24691, (long long)3885909283);
    
    char *errmsg = NULL;
    rc = sqlite3_exec(db_conn, sql, NULL, NULL, &errmsg);
    if (rc != SQLITE_OK) {
        fprintf(stderr, "Failed to create LFSR function info: %s\n", errmsg);
        sqlite3_free(errmsg);
    } else {
        fprintf(stderr, "Created LFSR function info in database\n");
    }
    sqlite3_free(sql);
}

/* Setup tracking tables */
static void setup_tracking_tables(void) {
    if (!db) {
        fprintf(stderr, "setup_tracking_tables: db is NULL\n");
        return;
    }
    
    /* Create basic superframes table first - it's needed by other functions */
    const char *superframes_sql = 
        "CREATE TABLE IF NOT EXISTS superframes ("
        " id INTEGER PRIMARY KEY,"
        " start_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,"
        " slot INTEGER,"
        " color_code INTEGER,"
        " sync_type TEXT,"
        " h_mi INTEGER,"
        " c_mi INTEGER,"
        " frame_count INTEGER DEFAULT 0,"
        " source_id INTEGER,"
        " target_id INTEGER,"
        " flco INTEGER,"
        " fid INTEGER,"
        " service_options INTEGER,"
        " group_call INTEGER DEFAULT 0,"
        " priority_call INTEGER DEFAULT 0,"
        " emergency_call INTEGER DEFAULT 0,"
        " encrypted INTEGER DEFAULT 0,"
        " manufacturer TEXT,"
        " privacy_algid INTEGER,"
        " data_format INTEGER,"
        " crc_passed INTEGER DEFAULT 1,"
        " session_id TEXT"
        ")";
    
    char *errmsg = NULL;
    int rc = sqlite3_exec(db, superframes_sql, NULL, NULL, &errmsg);
    if (rc != SQLITE_OK) {
        fprintf(stderr, "SQL error creating superframes table: %s\n", errmsg);
        sqlite3_free(errmsg);
        errmsg = NULL;
    } else {
        fprintf(stderr, "Successfully created superframes table\n");
    }
    
    /* Create session tracking table */
    const char *session_sql = 
        "CREATE TABLE IF NOT EXISTS capture_sessions ("
        "  id INTEGER PRIMARY KEY, "
        "  session_id TEXT UNIQUE, "
        "  start_time DATETIME DEFAULT CURRENT_TIMESTAMP, "
        "  end_time DATETIME, "
        "  description TEXT"
        ")";
    
    sqlite3_exec(db, session_sql, NULL, NULL, &errmsg);
    if (errmsg) {
        fprintf(stderr, "SQL error: %s\n", errmsg);
        sqlite3_free(errmsg);
        errmsg = NULL;
    }
    
    /* Check if table was created successfully */
    int have_sessions_table = 0;
    char *check_sql = "SELECT name FROM sqlite_master WHERE type='table' AND name='capture_sessions'";
    sqlite3_stmt *stmt;
    if (sqlite3_prepare_v2(db, check_sql, -1, &stmt, NULL) == SQLITE_OK) {
        if (sqlite3_step(stmt) == SQLITE_ROW) {
            have_sessions_table = 1;
        }
        sqlite3_finalize(stmt);
    }
    
    /* Only try to insert if table exists */
    if (have_sessions_table) {
        /* Insert current session */
        char *session_insert = sqlite3_mprintf(
                "INSERT OR IGNORE INTO capture_sessions (session_id) VALUES ('%q')",
                current_capture_session);
        
        sqlite3_exec(db, session_insert, NULL, NULL, &errmsg);
        if (errmsg) {
            fprintf(stderr, "SQL error: %s\n", errmsg);
            sqlite3_free(errmsg);
            errmsg = NULL;
        }
        sqlite3_free(session_insert);
    } else {
        fprintf(stderr, "Failed to create capture_sessions table\n");
    }
    
    /* Create auto correlations table */
    const char *auto_corr_sql =
        "CREATE TABLE IF NOT EXISTS dmr_auto_correlations ("
        "  id INTEGER PRIMARY KEY,"
        "  header_mi INTEGER,"
        "  content_mi INTEGER,"
        "  prev_mi INTEGER,"
        "  predicted_next_mi INTEGER,"
        "  actual_next_mi INTEGER,"
        "  slot INTEGER,"
        "  algid INTEGER,"
        "  key_id INTEGER,"
        "  first_frame_id INTEGER,"
        "  last_frame_id INTEGER,"
        "  first_timestamp DATETIME,"
        "  last_timestamp DATETIME,"
        "  frame_count INTEGER DEFAULT 1,"
        "  session_id TEXT,"
        "  UNIQUE(content_mi, slot)"
        ")";
    
    sqlite3_exec(db, auto_corr_sql, NULL, NULL, &errmsg);
    if (errmsg) {
        fprintf(stderr, "SQL error creating dmr_auto_correlations: %s\n", errmsg);
        sqlite3_free(errmsg);
        errmsg = NULL;
    }
    
    /* Create LFSR state tracking table */
    const char *lfsr_track_sql =
        "CREATE TABLE IF NOT EXISTS lfsr_state_tracking ("
        "  id INTEGER PRIMARY KEY,"
        "  current_mi INTEGER,"
        "  slot INTEGER,"
        "  expected_next_mi INTEGER,"
        "  timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,"
        "  UNIQUE(slot)"
        ")";
    
    sqlite3_exec(db, lfsr_track_sql, NULL, NULL, &errmsg);
    if (errmsg) {
        fprintf(stderr, "SQL error creating lfsr_state_tracking: %s\n", errmsg);
        sqlite3_free(errmsg);
        errmsg = NULL;
    }
    
    /* Check if LFSR tracking table was created successfully */
    int have_lfsr_table = 0;
    check_sql = "SELECT name FROM sqlite_master WHERE type='table' AND name='lfsr_state_tracking'";
    if (sqlite3_prepare_v2(db, check_sql, -1, &stmt, NULL) == SQLITE_OK) {
        if (sqlite3_step(stmt) == SQLITE_ROW) {
            have_lfsr_table = 1;
        }
        sqlite3_finalize(stmt);
    }
    
    /* Only try to insert if table exists */
    if (have_lfsr_table) {
        /* Initialize LFSR tracking */
        const char *init_lfsr_sql =
            "INSERT OR IGNORE INTO lfsr_state_tracking (current_mi, slot, expected_next_mi) "
            "VALUES (0, 0, 0), (0, 1, 0)";
        
        sqlite3_exec(db, init_lfsr_sql, NULL, NULL, &errmsg);
        if (errmsg) {
            fprintf(stderr, "SQL error initializing LFSR tracking: %s\n", errmsg);
            sqlite3_free(errmsg);
            errmsg = NULL;
        }
    } else {
        fprintf(stderr, "Failed to create lfsr_state_tracking table\n");
    }
    
    /* Create LFSR analytics table */
    const char *lfsr_analytics_sql =
        "CREATE TABLE IF NOT EXISTS lfsr_analytics ("
        "  id INTEGER PRIMARY KEY,"
        "  polynomial TEXT DEFAULT 'x^32 + x^4 + x^2 + 1',"
        "  missing_constant INTEGER DEFAULT 1,"
        "  observed_cycle_length INTEGER,"
        "  theoretical_cycle_length INTEGER DEFAULT 32767,"
        "  unique_mi_values INTEGER,"
        "  observation_quality REAL,"
        "  analysis_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP"
        ")";
    
    sqlite3_exec(db, lfsr_analytics_sql, NULL, NULL, &errmsg);
    if (errmsg) {
        fprintf(stderr, "SQL error creating lfsr_analytics: %s\n", errmsg);
        sqlite3_free(errmsg);
        errmsg = NULL;
    }
    
    /* Initialize lfsr_analytics with a default row */
    const char *init_analytics_sql =
        "INSERT OR IGNORE INTO lfsr_analytics "
        "(polynomial, missing_constant, theoretical_cycle_length) "
        "VALUES ('x^32 + x^4 + x^2 + 1', 1, 32767)";
    
    sqlite3_exec(db, init_analytics_sql, NULL, NULL, &errmsg);
    if (errmsg) {
        fprintf(stderr, "SQL error initializing analytics: %s\n", errmsg);
        sqlite3_free(errmsg);
    }
}

/* Setup triggers for auto-correlation */
static void setup_triggers(void) {
    if (!db) return;
    
    char *errmsg = NULL;
    
    /* Begin transaction for creating all triggers */
    if (sqlite3_exec(db, "BEGIN TRANSACTION", NULL, NULL, &errmsg) != SQLITE_OK) {
        fprintf(stderr, "Failed to begin transaction for triggers: %s\n", errmsg);
        sqlite3_free(errmsg);
        errmsg = NULL;
    }
    
    /* Trigger for superframe inserts */
    const char *superframe_trigger =
        "CREATE TRIGGER IF NOT EXISTS after_superframe_insert "
        "AFTER INSERT ON superframes "
        "BEGIN "
        "  /* Add to correlation table if MI values or privacy_algid indicate encryption */ "
        "  INSERT OR IGNORE INTO dmr_auto_correlations "
        "    (header_mi, content_mi, slot, algid, first_timestamp, last_timestamp, session_id) "
        "  SELECT "
        "    NEW.h_mi, "
        "    NEW.c_mi, "
        "    NEW.slot, "
        "    NEW.privacy_algid, "
        "    NEW.start_timestamp, "
        "    NEW.start_timestamp, "
        "    (SELECT session_id FROM capture_sessions ORDER BY id DESC LIMIT 1) "
        "  WHERE (NEW.encrypted = 1) OR "
        "        (NEW.h_mi > 0) OR "
        "        (NEW.c_mi > 0) OR "
        "        (NEW.privacy_algid > 0); "
        
        "  /* Update correlations if entry exists */ "
        "  UPDATE dmr_auto_correlations "
        "  SET "
        "    last_timestamp = NEW.start_timestamp, "
        "    frame_count = frame_count + 1 "
        "  WHERE content_mi = NEW.c_mi AND slot = NEW.slot; "
        
        "  /* Calculate and store LFSR prediction */ "
        "  UPDATE dmr_auto_correlations "
        "  SET predicted_next_mi = lfsr_32_steps(content_mi) "
        "  WHERE content_mi = NEW.c_mi AND slot = NEW.slot "
        "  AND predicted_next_mi IS NULL; "
        
        "  /* Get the previous tracked MI for this slot */ "
        "  UPDATE dmr_auto_correlations "
        "  SET actual_next_mi = NEW.c_mi "
        "  WHERE content_mi = ( "
        "    SELECT current_mi FROM lfsr_state_tracking "
        "    WHERE slot = NEW.slot "
        "  ) AND slot = NEW.slot; "
        
        "  /* Update LFSR state tracking */ "
        "  UPDATE lfsr_state_tracking "
        "  SET "
        "    current_mi = NEW.c_mi, "
        "    expected_next_mi = lfsr_32_steps(NEW.c_mi), "
        "    timestamp = NEW.start_timestamp "
        "  WHERE slot = NEW.slot; "
        "END";
    
    int rc = sqlite3_exec(db, superframe_trigger, NULL, NULL, &errmsg);
    if (rc != SQLITE_OK) {
        fprintf(stderr, "SQL error creating superframe trigger: %s\n", errmsg);
        sqlite3_free(errmsg);
        errmsg = NULL;
    } else {
        fprintf(stderr, "Successfully created superframe trigger\n");
    }
    
    /* Simplified trigger for LFSR chain analysis - less likely to cause locks */
    const char *analysis_trigger =
        "CREATE TRIGGER IF NOT EXISTS analyze_lfsr_chain "
        "AFTER INSERT ON dmr_auto_correlations "
        "WHEN (SELECT COUNT(*) FROM dmr_auto_correlations) % 25 = 0 "
        "BEGIN "
        "  /* Update LFSR analytics - simplified to avoid recursive lock */ "
        "  INSERT OR REPLACE INTO lfsr_analytics "
        "    (unique_mi_values, observation_quality) "
        "  SELECT "
        "    COUNT(DISTINCT content_mi), "
        "    ( "
        "      SELECT 100.0 * SUM(CASE WHEN predicted_next_mi = actual_next_mi THEN 1 ELSE 0 END) / "
        "             NULLIF(COUNT(*), 0) "
        "      FROM dmr_auto_correlations "
        "      WHERE predicted_next_mi IS NOT NULL AND actual_next_mi IS NOT NULL "
        "    ) "
        "  FROM dmr_auto_correlations; "
        "END";
    
    rc = sqlite3_exec(db, analysis_trigger, NULL, NULL, &errmsg);
    if (rc != SQLITE_OK) {
        fprintf(stderr, "SQL error creating analysis trigger: %s\n", errmsg);
        sqlite3_free(errmsg);
        errmsg = NULL;
    } else {
        fprintf(stderr, "Successfully created analysis trigger\n");
    }
    
    /* Trigger to link MI chain */
    const char *link_trigger =
        "CREATE TRIGGER IF NOT EXISTS link_mi_chain "
        "AFTER INSERT ON dmr_auto_correlations "
        "BEGIN "
        "  /* Find any correlation where this new MI is the predicted next */ "
        "  UPDATE dmr_auto_correlations "
        "  SET actual_next_mi = NEW.content_mi "
        "  WHERE predicted_next_mi = NEW.content_mi AND slot = NEW.slot; "
        
        "  /* Set this MI's previous in the chain */ "
        "  UPDATE dmr_auto_correlations "
        "  SET prev_mi = ( "
        "    SELECT content_mi FROM dmr_auto_correlations "
        "    WHERE predicted_next_mi = NEW.content_mi AND slot = NEW.slot "
        "    LIMIT 1 "
        "  ) "
        "  WHERE id = NEW.id; "
        "END";
    
    rc = sqlite3_exec(db, link_trigger, NULL, NULL, &errmsg);
    if (rc != SQLITE_OK) {
        fprintf(stderr, "SQL error creating link trigger: %s\n", errmsg);
        sqlite3_free(errmsg);
        errmsg = NULL;
    } else {
        fprintf(stderr, "Successfully created link trigger\n");
    }
    
    /* Commit the transaction */
    rc = sqlite3_exec(db, "COMMIT", NULL, NULL, &errmsg);
    if (rc != SQLITE_OK) {
        fprintf(stderr, "Failed to commit trigger transaction: %s\n", errmsg);
        sqlite3_free(errmsg);
    } else {
        fprintf(stderr, "Triggers created in transaction\n");
    }
}

/* Archive current database and create a new one */
void db_archive_and_create_new(void) {
    if (db) {
        /* Close current database */
        sqlite3_close(db);
        db = NULL;
    }
    
    struct stat st = {0};
    if (current_db_path[0] != '\0' && stat(current_db_path, &st) == 0 && st.st_size > 0) {
        /* Generate archive filename with timestamp */
        char archive_path[2048]; /* Increased buffer size to safely accommodate paths */
        time_t now;
        struct tm *tm_info;
        
        time(&now);
        tm_info = localtime(&now);
        
        char timestamp[32];
        strftime(timestamp, sizeof(timestamp), "%Y%m%d_%H%M%S", tm_info);
        
        snprintf(archive_path, sizeof(archive_path), 
                 "%s/dmr_capture_%s.db", 
                 archive_dir, timestamp);
        
        /* Copy current database to archive */
        FILE *src = fopen(current_db_path, "rb");
        if (src) {
            FILE *dst = fopen(archive_path, "wb");
            if (dst) {
                char buffer[8192];
                size_t bytes;
                
                while ((bytes = fread(buffer, 1, sizeof(buffer), src)) > 0) {
                    fwrite(buffer, 1, bytes, dst);
                }
                
                fclose(dst);
                fprintf(stderr, "db_logger: Archived database to %s\n", archive_path);
            }
            fclose(src);
        }
        
        /* Consolidate with master database */
        db_consolidate_with_master();
        
        /* Remove or truncate current database */
        unlink(current_db_path);
    }
    
    /* Initialize a new database */
    db_init_with_triggers();
}

/* Initialize the database system with triggers */
void db_init_with_triggers(void) {
    if (db) return; /* Already initialized */
    
    /* Get current directory */
    char cwd[256];
    if (getcwd(cwd, sizeof(cwd)) == NULL) {
        fprintf(stderr, "db_logger: Cannot get current directory\n");
        return;
    }
    
    /* Generate paths */
    snprintf(current_db_path, sizeof(current_db_path), 
             "%s/current_capture.db", cwd);
    snprintf(master_db_path, sizeof(master_db_path),
             "%s/dmr_master.db", cwd);
    snprintf(archive_dir, sizeof(archive_dir), 
             "%s/archives", cwd);
    
    /* Create archives directory if it doesn't exist */
    struct stat st = {0};
    if (stat(archive_dir, &st) == -1) {
        mkdir(archive_dir, 0750);
    }
    
    /* Generate timestamp for session ID */
    time_t now;
    struct tm *tm_info;
    time(&now);
    tm_info = localtime(&now);
    
    strftime(current_capture_session, sizeof(current_capture_session), 
             "SESSION_%Y%m%d_%H%M%S", tm_info);
    
    /* Create/open database with enhanced settings for concurrency */
    /* Use URI format to specify additional options */
    char db_uri[2048]; /* Increased buffer size to safely accommodate paths */
    snprintf(db_uri, sizeof(db_uri), "file:%s?mode=rwc&cache=shared", current_db_path);
    
    int rc = sqlite3_open_v2(db_uri, &db, 
                          SQLITE_OPEN_READWRITE | SQLITE_OPEN_CREATE | SQLITE_OPEN_URI |
                          SQLITE_OPEN_NOMUTEX, /* Allow multi-threaded access */
                          NULL);
    
    if (rc != SQLITE_OK) {
        fprintf(stderr, "db_logger: cannot open database %s: %s\n", 
                current_db_path, sqlite3_errmsg(db));
        sqlite3_close(db);
        db = NULL;
        return;
    }
    
    fprintf(stderr, "db_logger: opened database %s\n", current_db_path);
    
    /* Setup for performance and improved concurrency */
    char *errmsg = NULL;
    
    /* Use WAL journal mode for better concurrency */
    rc = sqlite3_exec(db, "PRAGMA journal_mode=WAL", NULL, NULL, &errmsg);
    if (rc != SQLITE_OK) {
        fprintf(stderr, "Error setting journal_mode: %s\n", errmsg);
        sqlite3_free(errmsg);
        errmsg = NULL;
    }
    
    /* Reduce durability guarantees for better performance */
    rc = sqlite3_exec(db, "PRAGMA synchronous=NORMAL", NULL, NULL, &errmsg);
    if (rc != SQLITE_OK) {
        fprintf(stderr, "Error setting synchronous: %s\n", errmsg);
        sqlite3_free(errmsg);
        errmsg = NULL;
    }
    
    /* Keep temp tables in memory */
    rc = sqlite3_exec(db, "PRAGMA temp_store=MEMORY", NULL, NULL, &errmsg);
    if (rc != SQLITE_OK) {
        fprintf(stderr, "Error setting temp_store: %s\n", errmsg);
        sqlite3_free(errmsg);
        errmsg = NULL;
    }
    
    /* Increase cache size for better performance */
    rc = sqlite3_exec(db, "PRAGMA cache_size=10000", NULL, NULL, &errmsg);
    if (rc != SQLITE_OK) {
        fprintf(stderr, "Error setting cache_size: %s\n", errmsg);
        sqlite3_free(errmsg);
        errmsg = NULL;
    }
    
    /* Increase busy timeout to wait longer for locks (10 seconds) */
    rc = sqlite3_exec(db, "PRAGMA busy_timeout=10000", NULL, NULL, &errmsg);
    if (rc != SQLITE_OK) {
        fprintf(stderr, "Error setting busy_timeout: %s\n", errmsg);
        sqlite3_free(errmsg);
        errmsg = NULL;
    }
    
    /* Set locking mode to EXCLUSIVE to avoid "database is locked" errors */
    rc = sqlite3_exec(db, "PRAGMA locking_mode=EXCLUSIVE", NULL, NULL, &errmsg);
    if (rc != SQLITE_OK) {
        fprintf(stderr, "Error setting locking_mode: %s\n", errmsg);
        sqlite3_free(errmsg);
        errmsg = NULL;
    }
    
    /* For DMR tables (disabled for compatibility) */
    rc = sqlite3_exec(db, "PRAGMA foreign_keys=OFF", NULL, NULL, &errmsg);
    if (rc != SQLITE_OK) {
        fprintf(stderr, "Error disabling foreign_keys: %s\n", errmsg);
        sqlite3_free(errmsg);
        errmsg = NULL;
    }
    
    /* Register LFSR functions */
    db_register_lfsr_functions(db);
    
    /* Check if there are existing superframes that need fixing */
    sqlite3_stmt *check_stmt;
    rc = sqlite3_prepare_v2(db, 
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='superframes'", 
        -1, &check_stmt, NULL);
    
    if (rc == SQLITE_OK) {
        if (sqlite3_step(check_stmt) == SQLITE_ROW) {
            int has_table = sqlite3_column_int(check_stmt, 0);
            if (has_table) {
                /* If superframes table exists, check for existing records */
                sqlite3_finalize(check_stmt);
                rc = sqlite3_prepare_v2(db, "SELECT COUNT(*) FROM superframes", -1, &check_stmt, NULL);
                
                if (rc == SQLITE_OK && sqlite3_step(check_stmt) == SQLITE_ROW) {
                    int count = sqlite3_column_int(check_stmt, 0);
                    if (count > 0) {
                        fprintf(stderr, "Found %d existing superframes, fixing encrypted flags...\n", count);
                        /* Fix any existing superframes with incorrect encrypted flags */
                        db_fix_encrypted_flags();
                    }
                }
            }
        }
        sqlite3_finalize(check_stmt);
    }
    
    /* Explicitly create critical superframes table first to ensure it exists */
    char *superframes_sql = sqlite3_mprintf(
        "CREATE TABLE IF NOT EXISTS superframes ("
        " id INTEGER PRIMARY KEY,"
        " start_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,"
        " slot INTEGER,"
        " color_code INTEGER,"
        " sync_type TEXT,"
        " h_mi INTEGER,"
        " c_mi INTEGER,"
        " frame_count INTEGER DEFAULT 0,"
        " source_id INTEGER,"
        " target_id INTEGER,"
        " flco INTEGER,"
        " fid INTEGER,"
        " service_options INTEGER,"
        " group_call INTEGER DEFAULT 0,"
        " priority_call INTEGER DEFAULT 0,"
        " emergency_call INTEGER DEFAULT 0,"
        " encrypted INTEGER DEFAULT 0,"
        " manufacturer TEXT,"
        " privacy_algid INTEGER,"
        " data_format INTEGER,"
        " crc_passed INTEGER DEFAULT 1,"
        " session_id TEXT DEFAULT '%q'"
        ")", current_capture_session);
    
    rc = sqlite3_exec(db, superframes_sql, NULL, NULL, &errmsg);
    if (rc != SQLITE_OK) {
        fprintf(stderr, "SQL error creating superframes table: %s\n", errmsg);
        sqlite3_free(errmsg);
        errmsg = NULL;
    } else {
        fprintf(stderr, "Successfully created superframes table in initialization\n");
    }
    sqlite3_free(superframes_sql);
    
    /* Create DMR correlations table (also critical) */
    char *correlations_sql = sqlite3_mprintf(
        "CREATE TABLE IF NOT EXISTS dmr_correlations ("
        " id INTEGER PRIMARY KEY,"
        " header_mi INTEGER,"
        " control_mi INTEGER,"
        " slot INTEGER,"
        " algid INTEGER,"
        " timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,"
        " UNIQUE(header_mi, control_mi, slot)"
        ")");
    
    rc = sqlite3_exec(db, correlations_sql, NULL, NULL, &errmsg);
    if (rc != SQLITE_OK) {
        fprintf(stderr, "SQL error creating dmr_correlations table: %s\n", errmsg);
        sqlite3_free(errmsg);
        errmsg = NULL;
    } else {
        fprintf(stderr, "Successfully created dmr_correlations table\n");
    }
    sqlite3_free(correlations_sql);
    
    /* Create all the tracking tables and triggers */
    setup_tracking_tables();
    setup_triggers();
    
    /* Prepare commonly used statements for better performance */
    fprintf(stderr, "Preparing common SQL statements...\n");
    
    /* Prepare statement to check if superframes table exists */
    const char *check_superframes_sql = "SELECT 1 FROM sqlite_master WHERE type='table' AND name='superframes'";
    rc = sqlite3_prepare_v2(db, check_superframes_sql, -1, &stmt_check_superframes, NULL);
    if (rc != SQLITE_OK) {
        fprintf(stderr, "Failed to prepare superframes check statement: %s\n", sqlite3_errmsg(db));
    }
    
    /* Prepare statement to insert into superframes */
    const char *insert_superframe_sql = 
        "INSERT INTO superframes (slot, color_code, sync_type, session_id) VALUES (?, ?, ?, ?)";
    rc = sqlite3_prepare_v2(db, insert_superframe_sql, -1, &stmt_insert_superframe, NULL);
    if (rc != SQLITE_OK) {
        fprintf(stderr, "Failed to prepare insert superframe statement: %s\n", sqlite3_errmsg(db));
    }
    
    /* Prepare statement to update superframe count */
    const char *update_superframe_sql = 
        "UPDATE superframes SET frame_count = ? WHERE id = ?";
    rc = sqlite3_prepare_v2(db, update_superframe_sql, -1, &stmt_update_superframe, NULL);
    if (rc != SQLITE_OK) {
        fprintf(stderr, "Failed to prepare update superframe statement: %s\n", sqlite3_errmsg(db));
    }
    
    /* Insert AMBE frame statement will be prepared on demand based on context */
    
    fprintf(stderr, "Database initialization complete\n");
}

/* Old initialization function for compatibility */
static void db_init(void) {
    if (!db) {
        db_init_with_triggers();
    }
}

void db_set_header_mi(uint64_t mi, int slot, uint32_t algid) {
    db_init();
    if (!db) return;
    current_h_mi = mi;
    current_context = 1;
    current_slot = slot;
    current_algid = algid;
    char tbl[64];
    snprintf(tbl, sizeof(tbl), "H_%08X_S%d", (uint32_t)(mi & 0xFFFFFFFF), slot);
    char *errmsg = NULL;
    char *sql = sqlite3_mprintf(
        "CREATE TABLE IF NOT EXISTS '%q' ("
        " id INTEGER PRIMARY KEY,"
        " ambe_hex TEXT,"
        " timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,"
        " mi_full INTEGER,"
        " algid INTEGER,"
        " slot INTEGER,"
        " superframe_id INTEGER,"
        " session_id TEXT DEFAULT '%q'"
        ");", tbl, current_capture_session);
    sqlite3_exec(db, sql, NULL, NULL, &errmsg);
    if (errmsg) {
        sqlite3_free(errmsg);
        errmsg = NULL;
    }
    sqlite3_free(sql);
    
    /* Also update the current superframe if we have one */
    if (current_superframe_id > 0) {
        fprintf(stderr, "Updating superframe %d with h_mi=%llu\n", 
                current_superframe_id, (unsigned long long)mi);
        
        sql = sqlite3_mprintf(
            "UPDATE superframes SET h_mi = %llu, privacy_algid = %u, encrypted = 1 "
            "WHERE id = %d",
            (unsigned long long)mi, algid, current_superframe_id);
        
        sqlite3_exec(db, sql, NULL, NULL, &errmsg);
        if (errmsg) {
            fprintf(stderr, "Error updating superframe h_mi: %s\n", errmsg);
            sqlite3_free(errmsg);
        }
        sqlite3_free(sql);
        
        /* Also ensure dmr_auto_correlations table is updated */
        db_update_encrypted_flag();
    }
}

void db_set_control_mi(uint32_t mi) {
    db_init();
    if (!db) return;
    current_c_mi = mi;
    current_context = 2;
    char tbl[64];
    snprintf(tbl, sizeof(tbl), "C_%08X_S%d", mi, current_slot);
    char *errmsg = NULL;
    char *sql = sqlite3_mprintf(
        "CREATE TABLE IF NOT EXISTS '%q' ("
        " id INTEGER PRIMARY KEY,"
        " ambe_hex TEXT,"
        " timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,"
        " mi_full INTEGER,"
        " algid INTEGER,"
        " slot INTEGER,"
        " superframe_id INTEGER,"
        " session_id TEXT DEFAULT '%q'"
        ");", tbl, current_capture_session);
    sqlite3_exec(db, sql, NULL, NULL, &errmsg);
    if (errmsg) {
        sqlite3_free(errmsg);
        errmsg = NULL;
    }
    sqlite3_free(sql);
    
    /* Update the current superframe if we have one */
    if (current_superframe_id > 0) {
        fprintf(stderr, "Updating superframe %d with c_mi=%u\n", current_superframe_id, mi);
        
        sql = sqlite3_mprintf(
            "UPDATE superframes SET c_mi = %u, encrypted = 1 WHERE id = %d",
            mi, current_superframe_id);
        
        sqlite3_exec(db, sql, NULL, NULL, &errmsg);
        if (errmsg) {
            fprintf(stderr, "Error updating superframe c_mi: %s\n", errmsg);
            sqlite3_free(errmsg);
        }
        sqlite3_free(sql);
        
        /* Also ensure dmr_auto_correlations table is updated */
        db_update_encrypted_flag();
    }
}

/* Keep track of AMBE frame batch counter to optimize transaction use */
static int ambe_frame_counter = 0;
static int in_ambe_transaction = 0;

void db_log_ambe(uint64_t ambe) {
    db_init();
    if (!db) return;
    
    /* Use transactions to improve performance for batches of frames */
    if (!in_ambe_transaction) {
        char *errmsg = NULL;
        int rc = sqlite3_exec(db, "BEGIN TRANSACTION", NULL, NULL, &errmsg);
        if (rc != SQLITE_OK) {
            fprintf(stderr, "Failed to begin transaction for AMBE logging: %s\n", errmsg);
            sqlite3_free(errmsg);
        } else {
            in_ambe_transaction = 1;
        }
    }
    
    char tbl[64];
    uint64_t current_mi = 0;
    
    if (current_context == 1 && current_h_mi != 0) {
        snprintf(tbl, sizeof(tbl), "H_%08X_S%d", (uint32_t)(current_h_mi & 0xFFFFFFFF), current_slot);
        current_mi = current_h_mi;
    } else if (current_context == 2 && current_c_mi != 0) {
        snprintf(tbl, sizeof(tbl), "C_%08X_S%d", current_c_mi, current_slot);
        current_mi = current_c_mi;
    } else {
        /* For unencrypted frames, use a default table */
        snprintf(tbl, sizeof(tbl), "U_00000000_S%d", current_slot);
        current_mi = 0;
    }
    
    /* Use dynamic statement cache - only check table once per session */
    static char last_tbl[64] = {0};
    static int last_tbl_exists = 0;
    
    /* Only check table existence if we haven't processed this table yet */
    if (strcmp(tbl, last_tbl) != 0) {
        /* Save for next time */
        strncpy(last_tbl, tbl, sizeof(last_tbl));
        last_tbl_exists = 0;
        
        /* Check if table exists */
        char *check_sql = sqlite3_mprintf(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='%q'", tbl);
        
        sqlite3_stmt *check_stmt;
        int rc = sqlite3_prepare_v2(db, check_sql, -1, &check_stmt, NULL);
        
        if (rc == SQLITE_OK) {
            rc = sqlite3_step(check_stmt);
            if (rc == SQLITE_ROW) {
                last_tbl_exists = 1;
            }
            sqlite3_finalize(check_stmt);
        }
        sqlite3_free(check_sql);
        
        if (!last_tbl_exists) {
            /* Create the table if it doesn't exist */
            char *create_sql = sqlite3_mprintf(
                "CREATE TABLE IF NOT EXISTS '%q' ("
                " id INTEGER PRIMARY KEY,"
                " ambe_hex TEXT,"
                " timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,"
                " mi_full INTEGER,"
                " algid INTEGER,"
                " slot INTEGER,"
                " superframe_id INTEGER,"
                " session_id TEXT DEFAULT '%q'"
                ");", tbl, current_capture_session);
            
            char *errmsg = NULL;
            rc = sqlite3_exec(db, create_sql, NULL, NULL, &errmsg);
            if (rc != SQLITE_OK) {
                fprintf(stderr, "Error creating AMBE table '%s': %s\n", tbl, errmsg);
                sqlite3_free(errmsg);
            } else {
                last_tbl_exists = 1;
            }
            sqlite3_free(create_sql);
        }
    }
    
    /* Convert AMBE to hex string */
    char ambe_hex[17];
    snprintf(ambe_hex, sizeof(ambe_hex), "%016llX", (unsigned long long)ambe);
    
    /* Prepare and use the insert statement on demand (dynamically for different tables) */
    char *insert_sql = sqlite3_mprintf(
        "INSERT INTO '%q' (ambe_hex, mi_full, algid, slot, superframe_id, session_id) "
        "VALUES (?, ?, ?, ?, ?, ?)", tbl);
    
    sqlite3_stmt *stmt;
    int rc = sqlite3_prepare_v2(db, insert_sql, -1, &stmt, NULL);
    if (rc == SQLITE_OK) {
        sqlite3_bind_text(stmt, 1, ambe_hex, -1, SQLITE_STATIC);
        sqlite3_bind_int64(stmt, 2, (sqlite3_int64)current_mi);
        sqlite3_bind_int(stmt, 3, current_algid);
        sqlite3_bind_int(stmt, 4, current_slot);
        sqlite3_bind_int(stmt, 5, current_superframe_id);
        sqlite3_bind_text(stmt, 6, current_capture_session, -1, SQLITE_STATIC);
        
        rc = sqlite3_step(stmt);
        if (rc != SQLITE_DONE) {
            fprintf(stderr, "Error inserting AMBE: %s\n", sqlite3_errmsg(db));
        }
        sqlite3_finalize(stmt);
    } else {
        fprintf(stderr, "Error preparing AMBE insert statement: %s\n", sqlite3_errmsg(db));
    }
    sqlite3_free(insert_sql);
    
    /* Only insert correlations if we have both MIs */
    if (current_h_mi != 0 && current_c_mi != 0) {
        char *corr_sql = sqlite3_mprintf(
            "INSERT OR IGNORE INTO dmr_correlations (header_mi, control_mi, slot, algid) "
            "VALUES (%llu, %u, %d, %u);",
            (unsigned long long)current_h_mi, current_c_mi, current_slot, current_algid);
        
        sqlite3_exec(db, corr_sql, NULL, NULL, NULL);
        sqlite3_free(corr_sql);
    }
    
    /* Increment frame count for the superframe */
    if (current_superframe_id > 0) {
        frame_count_in_superframe++;
    }
    
    /* Commit every 50 frames to avoid long-running transactions */
    ambe_frame_counter++;
    if (ambe_frame_counter >= 50 && in_ambe_transaction) {
        char *errmsg = NULL;
        int rc = sqlite3_exec(db, "COMMIT", NULL, NULL, &errmsg);
        if (rc != SQLITE_OK) {
            fprintf(stderr, "Failed to commit AMBE transaction: %s\n", errmsg);
            sqlite3_free(errmsg);
        }
        in_ambe_transaction = 0;
        ambe_frame_counter = 0;
    }
}

void db_start_superframe(int slot, int color_code, const char *sync_type) {
    db_init();
    if (!db) return;
    
    /* Check if superframes table exists using prepared statement */
    int superframes_exists = 0;
    int rc;
    
    if (stmt_check_superframes) {
        sqlite3_reset(stmt_check_superframes);
        rc = sqlite3_step(stmt_check_superframes);
        if (rc == SQLITE_ROW) {
            superframes_exists = 1;
        } else if (rc != SQLITE_DONE) {
            fprintf(stderr, "Error checking superframes table: %s\n", sqlite3_errmsg(db));
        }
    } else {
        /* Fallback if the prepared statement wasn't created */
        fprintf(stderr, "WARNING: stmt_check_superframes not prepared, using direct query\n");
        sqlite3_stmt *stmt;
        rc = sqlite3_prepare_v2(db, "SELECT 1 FROM sqlite_master WHERE type='table' AND name='superframes'", -1, &stmt, NULL);
        if (rc == SQLITE_OK) {
            rc = sqlite3_step(stmt);
            if (rc == SQLITE_ROW) {
                superframes_exists = 1;
            }
            sqlite3_finalize(stmt);
        }
    }
    
    /* Create superframes table if needed */
    if (!superframes_exists) {
        fprintf(stderr, "Superframes table not found, creating it now\n");
        char *sql = sqlite3_mprintf(
            "CREATE TABLE IF NOT EXISTS superframes ("
            " id INTEGER PRIMARY KEY,"
            " start_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,"
            " slot INTEGER,"
            " color_code INTEGER,"
            " sync_type TEXT,"
            " h_mi INTEGER,"
            " c_mi INTEGER,"
            " frame_count INTEGER DEFAULT 0,"
            " source_id INTEGER,"
            " target_id INTEGER,"
            " flco INTEGER,"
            " fid INTEGER,"
            " service_options INTEGER,"
            " group_call INTEGER DEFAULT 0,"
            " priority_call INTEGER DEFAULT 0,"
            " emergency_call INTEGER DEFAULT 0,"
            " encrypted INTEGER DEFAULT 0,"
            " manufacturer TEXT,"
            " privacy_algid INTEGER,"
            " data_format INTEGER,"
            " crc_passed INTEGER DEFAULT 1,"
            " session_id TEXT DEFAULT '%q'"
            ");", current_capture_session);
        
        char *errmsg = NULL;
        rc = sqlite3_exec(db, sql, NULL, NULL, &errmsg);
        if (rc != SQLITE_OK) {
            fprintf(stderr, "SQL error in db_start_superframe: %s\n", errmsg);
            sqlite3_free(errmsg);
        } else {
            fprintf(stderr, "Successfully created superframes table in db_start_superframe\n");
        }
        sqlite3_free(sql);
    }
    
    /* Use prepared statement to insert a new superframe */
    if (stmt_insert_superframe) {
        /* Reset statement and bind parameters */
        sqlite3_reset(stmt_insert_superframe);
        sqlite3_clear_bindings(stmt_insert_superframe);
        
        sqlite3_bind_int(stmt_insert_superframe, 1, slot);
        sqlite3_bind_int(stmt_insert_superframe, 2, color_code);
        sqlite3_bind_text(stmt_insert_superframe, 3, sync_type, -1, SQLITE_STATIC);
        sqlite3_bind_text(stmt_insert_superframe, 4, current_capture_session, -1, SQLITE_STATIC);
        
        /* Execute the statement */
        rc = sqlite3_step(stmt_insert_superframe);
        if (rc != SQLITE_DONE) {
            fprintf(stderr, "Error inserting superframe: %s\n", sqlite3_errmsg(db));
        } else {
            /* Get the ID of the inserted superframe */
            current_superframe_id = sqlite3_last_insert_rowid(db);
            current_slot = slot;
            frame_count_in_superframe = 0;
            
            if (current_superframe_id > 0) {
                fprintf(stderr, "Started new superframe ID %d\n", current_superframe_id);
            }
        }
    } else {
        /* Fallback if prepared statement wasn't created */
        fprintf(stderr, "WARNING: stmt_insert_superframe not prepared, using direct query\n");
        char *sql = sqlite3_mprintf(
            "INSERT INTO superframes (slot, color_code, sync_type, session_id) "
            "VALUES (%d, %d, '%q', '%q');",
            slot, color_code, sync_type, current_capture_session);
        
        char *errmsg = NULL;
        rc = sqlite3_exec(db, sql, NULL, NULL, &errmsg);
        if (rc != SQLITE_OK) {
            fprintf(stderr, "SQL error inserting superframe: %s\n", errmsg);
            sqlite3_free(errmsg);
        } else {
            /* Get the ID of the inserted superframe */
            current_superframe_id = sqlite3_last_insert_rowid(db);
            current_slot = slot;
            frame_count_in_superframe = 0;
        }
        sqlite3_free(sql);
    }
}

void db_end_superframe(void) {
    if (!db || current_superframe_id <= 0) return;
    
    /* Update frame count using prepared statement */
    if (stmt_update_superframe) {
        sqlite3_reset(stmt_update_superframe);
        sqlite3_clear_bindings(stmt_update_superframe);
        
        sqlite3_bind_int(stmt_update_superframe, 1, frame_count_in_superframe);
        sqlite3_bind_int(stmt_update_superframe, 2, current_superframe_id);
        
        int rc = sqlite3_step(stmt_update_superframe);
        if (rc != SQLITE_DONE) {
            fprintf(stderr, "Error updating superframe count: %s\n", sqlite3_errmsg(db));
        }
    } else {
        /* Fallback if prepared statement wasn't created */
        char *sql = sqlite3_mprintf(
            "UPDATE superframes SET frame_count = %d WHERE id = %d;",
            frame_count_in_superframe, current_superframe_id);
        
        sqlite3_exec(db, sql, NULL, NULL, NULL);
        sqlite3_free(sql);
    }
    
    /* Update MI values if we have them */
    if (current_h_mi != 0 || current_c_mi != 0) {
        /* This is less frequent, so direct SQL instead of prepared statement */
        char *sql = sqlite3_mprintf(
            "UPDATE superframes SET h_mi = %llu, c_mi = %u WHERE id = %d;",
            (unsigned long long)current_h_mi, current_c_mi, current_superframe_id);
        
        sqlite3_exec(db, sql, NULL, NULL, NULL);
        sqlite3_free(sql);
    }
    
    if (frame_count_in_superframe > 0) {
        fprintf(stderr, "Ended superframe ID %d with %d frames\n", 
                current_superframe_id, frame_count_in_superframe);
    }
    
    /* Reset state for next superframe */
    current_superframe_id = 0;
    current_h_mi = 0;
    current_c_mi = 0;
    current_context = 0;
}

void db_set_radio_ids(uint32_t source, uint32_t target) {
    if (!db || current_superframe_id <= 0) return;
    
    char *sql = sqlite3_mprintf(
        "UPDATE superframes SET source_id = %u, target_id = %u WHERE id = %d;",
        source, target, current_superframe_id);
    
    sqlite3_exec(db, sql, NULL, NULL, NULL);
    sqlite3_free(sql);
}

void db_set_flco_metadata(uint8_t flco, uint8_t fid, uint8_t so, const char *manufacturer) {
    if (!db || current_superframe_id <= 0) return;
    
    char *sql = sqlite3_mprintf(
        "UPDATE superframes SET flco = %u, fid = %u, service_options = %u, manufacturer = '%q' WHERE id = %d;",
        flco, fid, so, manufacturer, current_superframe_id);
    
    sqlite3_exec(db, sql, NULL, NULL, NULL);
    sqlite3_free(sql);
}

void db_set_call_flags(int group_call, int priority_call, int emergency_call, int encrypted) {
    if (!db || current_superframe_id <= 0) return;
    
    char *sql = sqlite3_mprintf(
        "UPDATE superframes SET group_call = %d, priority_call = %d, "
        "emergency_call = %d, encrypted = %d WHERE id = %d;",
        group_call, priority_call, emergency_call, encrypted, current_superframe_id);
    
    sqlite3_exec(db, sql, NULL, NULL, NULL);
    sqlite3_free(sql);
}

void db_set_privacy_info(uint32_t algid, int data_format) {
    if (!db || current_superframe_id <= 0) return;
    
    char *sql = sqlite3_mprintf(
        "UPDATE superframes SET privacy_algid = %u, data_format = %d WHERE id = %d;",
        algid, data_format, current_superframe_id);
    
    sqlite3_exec(db, sql, NULL, NULL, NULL);
    sqlite3_free(sql);
}

void db_set_crc_status(int crc_passed) {
    if (!db || current_superframe_id <= 0) return;
    
    char *sql = sqlite3_mprintf(
        "UPDATE superframes SET crc_passed = %d WHERE id = %d;",
        crc_passed, current_superframe_id);
    
    sqlite3_exec(db, sql, NULL, NULL, NULL);
    sqlite3_free(sql);
}

void db_set_talkgroup(uint32_t talkgroup) {
    if (!db || current_superframe_id <= 0) return;
    
    /* Create metadata table if it doesn't exist */
    char *sql = sqlite3_mprintf(
        "CREATE TABLE IF NOT EXISTS dmr_metadata ("
        " id INTEGER PRIMARY KEY,"
        " talkgroup INTEGER,"
        " superframe_id INTEGER,"
        " timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,"
        " session_id TEXT DEFAULT '%q'"
        ");", current_capture_session);
    
    sqlite3_exec(db, sql, NULL, NULL, NULL);
    sqlite3_free(sql);
    
    /* Insert metadata */
    sql = sqlite3_mprintf(
        "INSERT INTO dmr_metadata (talkgroup, superframe_id) VALUES (%u, %d);",
        talkgroup, current_superframe_id);
    
    sqlite3_exec(db, sql, NULL, NULL, NULL);
    sqlite3_free(sql);
}

void db_update_encrypted_flag(void) {
    if (!db || current_superframe_id <= 0) return;
    
    /* Check multiple indicators of encryption, not just MI values */
    int is_encrypted = 0;
    
    /* Check if any of the encryption indicators are present */
    if (current_h_mi != 0 || current_c_mi != 0 || current_algid != 0) {
        is_encrypted = 1;
    }
    
    /* Update the flag if encrypted */
    if (is_encrypted) {
        char *sql = sqlite3_mprintf(
            "UPDATE superframes SET encrypted = 1 WHERE id = %d;",
            current_superframe_id);
        
        sqlite3_exec(db, sql, NULL, NULL, NULL);
        sqlite3_free(sql);
        
        /* Also force an update of the dmr_auto_correlations table */
        sql = sqlite3_mprintf(
            "INSERT OR IGNORE INTO dmr_auto_correlations "
            "(header_mi, content_mi, slot, algid, first_timestamp, last_timestamp, session_id) "
            "SELECT h_mi, c_mi, slot, privacy_algid, start_timestamp, start_timestamp, session_id "
            "FROM superframes WHERE id = %d AND (h_mi > 0 OR c_mi > 0 OR privacy_algid > 0);",
            current_superframe_id);
            
        sqlite3_exec(db, sql, NULL, NULL, NULL);
        sqlite3_free(sql);
    }
}

/* Copy a table between databases */
static void copy_table(sqlite3 *src_db, sqlite3 *dst_db, const char *table_name) {
    sqlite3_stmt *src_stmt;
    char *err_msg = NULL;
    
    /* Check if table exists in destination */
    char check_sql[256];
    snprintf(check_sql, sizeof(check_sql), 
            "SELECT name FROM sqlite_master WHERE type='table' AND name='%s'",
            table_name);
    
    sqlite3_stmt *check_stmt;
    int table_exists = 0;
    
    if (sqlite3_prepare_v2(dst_db, check_sql, -1, &check_stmt, NULL) == SQLITE_OK) {
        table_exists = (sqlite3_step(check_stmt) == SQLITE_ROW);
        sqlite3_finalize(check_stmt);
    }
    
    /* Create table in destination if needed */
    if (!table_exists) {
        /* Get table schema from source */
        char schema_sql[2048];
        sqlite3_stmt *schema_stmt;
        
        snprintf(schema_sql, sizeof(schema_sql),
                "SELECT sql FROM sqlite_master WHERE type='table' AND name='%s'",
                table_name);
                
        if (sqlite3_prepare_v2(src_db, schema_sql, -1, &schema_stmt, NULL) == SQLITE_OK) {
            if (sqlite3_step(schema_stmt) == SQLITE_ROW) {
                const char *create_sql = (const char*)sqlite3_column_text(schema_stmt, 0);
                
                /* Execute in destination */
                sqlite3_exec(dst_db, create_sql, NULL, NULL, &err_msg);
                if (err_msg) {
                    fprintf(stderr, "Error creating table %s: %s\n", table_name, err_msg);
                    sqlite3_free(err_msg);
                }
            }
            sqlite3_finalize(schema_stmt);
        }
    }
    
    /* Now copy data */
    char select_sql[128];
    snprintf(select_sql, sizeof(select_sql), "SELECT * FROM '%s'", table_name);
    
    if (sqlite3_prepare_v2(src_db, select_sql, -1, &src_stmt, NULL) == SQLITE_OK) {
        int col_count = sqlite3_column_count(src_stmt);
        
        /* Process each row */
        while (sqlite3_step(src_stmt) == SQLITE_ROW) {
            /* Build insert statement */
            char *insert_sql = sqlite3_mprintf("INSERT OR IGNORE INTO '%q' VALUES (", table_name);
            
            for (int i = 0; i < col_count; i++) {
                char *tmp_sql = NULL;
                
                if (i > 0) {
                    tmp_sql = sqlite3_mprintf("%s, ", insert_sql);
                    sqlite3_free(insert_sql);
                    insert_sql = tmp_sql;
                }
                
                switch (sqlite3_column_type(src_stmt, i)) {
                    case SQLITE_INTEGER:
                        tmp_sql = sqlite3_mprintf("%s%lld", insert_sql, sqlite3_column_int64(src_stmt, i));
                        break;
                    case SQLITE_FLOAT:
                        tmp_sql = sqlite3_mprintf("%s%f", insert_sql, sqlite3_column_double(src_stmt, i));
                        break;
                    case SQLITE_TEXT:
                        tmp_sql = sqlite3_mprintf("%s'%q'", insert_sql, sqlite3_column_text(src_stmt, i));
                        break;
                    case SQLITE_NULL:
                        tmp_sql = sqlite3_mprintf("%sNULL", insert_sql);
                        break;
                    case SQLITE_BLOB: {
                        const void *blob = sqlite3_column_blob(src_stmt, i);
                        int size = sqlite3_column_bytes(src_stmt, i);
                        tmp_sql = sqlite3_mprintf("%sX'", insert_sql);
                        
                        for (int j = 0; j < size; j++) {
                            char *hex_sql = sqlite3_mprintf("%s%02X", tmp_sql, ((unsigned char*)blob)[j]);
                            sqlite3_free(tmp_sql);
                            tmp_sql = hex_sql;
                        }
                        
                        char *final_sql = sqlite3_mprintf("%s'", tmp_sql);
                        sqlite3_free(tmp_sql);
                        tmp_sql = final_sql;
                        break;
                    }
                }
                
                sqlite3_free(insert_sql);
                insert_sql = tmp_sql;
            }
            
            char *final_sql = sqlite3_mprintf("%s)", insert_sql);
            sqlite3_free(insert_sql);
            insert_sql = final_sql;
            
            /* Execute insert */
            sqlite3_exec(dst_db, insert_sql, NULL, NULL, &err_msg);
            if (err_msg) {
                fprintf(stderr, "Error copying data: %s\n", err_msg);
                sqlite3_free(err_msg);
            }
            
            sqlite3_free(insert_sql);
        }
        
        sqlite3_finalize(src_stmt);
    }
}

/* Setup tables in master database */
static void setup_master_tables(sqlite3 *master_db) {
    if (!master_db) return;
    
    /* Create tables that we know we need */
    const char *tables_sql = 
        "CREATE TABLE IF NOT EXISTS superframes ("
        " id INTEGER PRIMARY KEY,"
        " start_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,"
        " slot INTEGER,"
        " color_code INTEGER,"
        " sync_type TEXT,"
        " h_mi INTEGER,"
        " c_mi INTEGER,"
        " frame_count INTEGER DEFAULT 0,"
        " source_id INTEGER,"
        " target_id INTEGER,"
        " flco INTEGER,"
        " fid INTEGER,"
        " service_options INTEGER,"
        " group_call INTEGER DEFAULT 0,"
        " priority_call INTEGER DEFAULT 0,"
        " emergency_call INTEGER DEFAULT 0,"
        " encrypted INTEGER DEFAULT 0,"
        " manufacturer TEXT,"
        " privacy_algid INTEGER,"
        " data_format INTEGER,"
        " crc_passed INTEGER DEFAULT 1,"
        " session_id TEXT"
        ");"
        
        "CREATE TABLE IF NOT EXISTS dmr_correlations ("
        " id INTEGER PRIMARY KEY,"
        " header_mi INTEGER,"
        " control_mi INTEGER,"
        " slot INTEGER,"
        " algid INTEGER,"
        " timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,"
        " UNIQUE(header_mi, control_mi, slot)"
        ");"
        
        "CREATE TABLE IF NOT EXISTS dmr_metadata ("
        " id INTEGER PRIMARY KEY,"
        " talkgroup INTEGER,"
        " superframe_id INTEGER,"
        " timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,"
        " session_id TEXT"
        ");"
        
        "CREATE TABLE IF NOT EXISTS capture_sessions ("
        " id INTEGER PRIMARY KEY,"
        " session_id TEXT UNIQUE,"
        " start_time DATETIME DEFAULT CURRENT_TIMESTAMP,"
        " end_time DATETIME,"
        " description TEXT"
        ");"
        
        "CREATE TABLE IF NOT EXISTS dmr_auto_correlations ("
        " id INTEGER PRIMARY KEY,"
        " header_mi INTEGER,"
        " content_mi INTEGER,"
        " prev_mi INTEGER,"
        " predicted_next_mi INTEGER,"
        " actual_next_mi INTEGER,"
        " slot INTEGER,"
        " algid INTEGER,"
        " key_id INTEGER,"
        " first_frame_id INTEGER,"
        " last_frame_id INTEGER,"
        " first_timestamp DATETIME,"
        " last_timestamp DATETIME,"
        " frame_count INTEGER DEFAULT 1,"
        " session_id TEXT,"
        " UNIQUE(content_mi, slot)"
        ");"
        
        "CREATE TABLE IF NOT EXISTS lfsr_analytics ("
        " id INTEGER PRIMARY KEY,"
        " polynomial TEXT DEFAULT 'x^32 + x^4 + x^2 + 1',"
        " missing_constant INTEGER DEFAULT 1,"
        " observed_cycle_length INTEGER,"
        " theoretical_cycle_length INTEGER DEFAULT 32767,"
        " unique_mi_values INTEGER,"
        " observation_quality REAL,"
        " analysis_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP"
        ");";
    
    sqlite3_exec(master_db, tables_sql, NULL, NULL, NULL);
}

/* Consolidate current database with master */
void db_consolidate_with_master(void) {
    sqlite3 *master_db = NULL;
    sqlite3 *current_db = NULL;
    
    if (current_db_path[0] == '\0' || master_db_path[0] == '\0') {
        fprintf(stderr, "db_logger: Cannot consolidate, paths not set\n");
        return;
    }
    
    /* Open master database (create if doesn't exist) */
    if (sqlite3_open(master_db_path, &master_db) != SQLITE_OK) {
        fprintf(stderr, "db_logger: Cannot open master database: %s\n", 
                sqlite3_errmsg(master_db));
        sqlite3_close(master_db);
        return;
    }
    
    /* Create tables in master if they don't exist */
    setup_master_tables(master_db);
    
    /* Open current database for reading */
    if (sqlite3_open_v2(current_db_path, &current_db, SQLITE_OPEN_READONLY, NULL) != SQLITE_OK) {
        fprintf(stderr, "db_logger: Cannot open current database: %s\n", 
                sqlite3_errmsg(current_db));
        sqlite3_close(current_db);
        sqlite3_close(master_db);
        return;
    }
    
    /* Start transaction */
    sqlite3_exec(master_db, "BEGIN TRANSACTION", NULL, NULL, NULL);
    
    /* Copy core tables */
    copy_table(current_db, master_db, "superframes");
    copy_table(current_db, master_db, "dmr_correlations");
    copy_table(current_db, master_db, "dmr_auto_correlations");
    copy_table(current_db, master_db, "dmr_metadata");
    copy_table(current_db, master_db, "capture_sessions");
    copy_table(current_db, master_db, "lfsr_analytics");
    
    /* Now copy MI tables - we need to detect them first */
    sqlite3_stmt *stmt;
    if (sqlite3_prepare_v2(current_db, 
                          "SELECT name FROM sqlite_master WHERE "
                          "type='table' AND (name LIKE 'C_%' OR name LIKE 'H_%' OR name LIKE 'U_%')",
                          -1, &stmt, NULL) == SQLITE_OK) {
        
        while (sqlite3_step(stmt) == SQLITE_ROW) {
            const char *table_name = (const char*)sqlite3_column_text(stmt, 0);
            copy_table(current_db, master_db, table_name);
        }
        
        sqlite3_finalize(stmt);
    }
    
    /* Commit transaction */
    sqlite3_exec(master_db, "COMMIT", NULL, NULL, NULL);
    
    sqlite3_close(current_db);
    sqlite3_close(master_db);
    
    fprintf(stderr, "db_logger: Consolidated database with master\n");
}

void db_close(void) {
    if (db) {
        /* 1. First, commit any pending transactions */
        if (in_ambe_transaction) {
            char *errmsg = NULL;
            int rc = sqlite3_exec(db, "COMMIT", NULL, NULL, &errmsg);
            if (rc != SQLITE_OK) {
                fprintf(stderr, "Failed to commit pending AMBE transaction during close: %s\n", errmsg);
                sqlite3_free(errmsg);
                errmsg = NULL;
            } else {
                fprintf(stderr, "Committed pending AMBE transaction during close\n");
            }
            in_ambe_transaction = 0;
            ambe_frame_counter = 0;
        }
        
        /* 2. Update session end time */
        if (current_capture_session[0] != '\0') {
            char *sql = sqlite3_mprintf(
                "UPDATE capture_sessions SET end_time = CURRENT_TIMESTAMP "
                "WHERE session_id = '%q'",
                current_capture_session);
            
            char *errmsg = NULL;
            int rc = sqlite3_exec(db, sql, NULL, NULL, &errmsg);
            if (rc != SQLITE_OK) {
                fprintf(stderr, "Failed to update session end time: %s\n", errmsg);
                sqlite3_free(errmsg);
            }
            sqlite3_free(sql);
        }
        
        /* 3. Finalize all prepared statements - MUST happen before checkpoint */
        if (stmt_check_superframes) {
            sqlite3_finalize(stmt_check_superframes);
            stmt_check_superframes = NULL;
        }
        
        if (stmt_insert_superframe) {
            sqlite3_finalize(stmt_insert_superframe);
            stmt_insert_superframe = NULL;
        }
        
        if (stmt_update_superframe) {
            sqlite3_finalize(stmt_update_superframe);
            stmt_update_superframe = NULL;
        }
        
        if (stmt_insert_ambe) {
            sqlite3_finalize(stmt_insert_ambe);
            stmt_insert_ambe = NULL;
        }
        
        /* 4. Update database settings to ensure safe closing */
        char *errmsg = NULL;
        int rc = sqlite3_exec(db, "PRAGMA locking_mode=NORMAL;", NULL, NULL, &errmsg);
        if (rc != SQLITE_OK) {
            fprintf(stderr, "Failed to set normal locking mode: %s\n", errmsg);
            sqlite3_free(errmsg);
            errmsg = NULL;
        }
        
        /* 5. Properly release all locks before checkpoint */
        rc = sqlite3_exec(db, "BEGIN IMMEDIATE; COMMIT;", NULL, NULL, &errmsg);
        if (rc != SQLITE_OK) {
            fprintf(stderr, "Failed to release locks: %s\n", errmsg);
            sqlite3_free(errmsg);
            errmsg = NULL;
        }
        
        /* 6. Checkpoint WAL files for durability */
        rc = sqlite3_exec(db, "PRAGMA wal_checkpoint(TRUNCATE);", NULL, NULL, &errmsg);
        if (rc != SQLITE_OK) {
            fprintf(stderr, "Failed to checkpoint WAL file: %s\n", errmsg);
            sqlite3_free(errmsg);
            errmsg = NULL;
            
            /* Try a passive checkpoint if truncate fails */
            rc = sqlite3_exec(db, "PRAGMA wal_checkpoint(PASSIVE);", NULL, NULL, &errmsg);
            if (rc != SQLITE_OK) {
                fprintf(stderr, "Failed to do passive checkpoint: %s\n", errmsg);
                sqlite3_free(errmsg);
                errmsg = NULL;
            } else {
                fprintf(stderr, "WAL file passive checkpointed\n");
            }
        } else {
            fprintf(stderr, "WAL file checkpointed and truncated successfully\n");
        }
        
        /* 7. Close the database connection with retry */
        int close_attempts = 0;
        const int max_close_attempts = 3;
        
        while (close_attempts < max_close_attempts) {
            rc = sqlite3_close(db);
            if (rc == SQLITE_OK) {
                fprintf(stderr, "Database connection closed cleanly\n");
                break;
            } else if (rc == SQLITE_BUSY) {
                fprintf(stderr, "Database busy during close attempt %d: %s\n", 
                        close_attempts + 1, sqlite3_errmsg(db));
                    
                /* Sleep briefly before retrying */
                usleep(100000); /* 100ms */
                close_attempts++;
                
                /* On last attempt, use sqlite3_close_v2 which is more aggressive */
                if (close_attempts == max_close_attempts - 1) {
                    fprintf(stderr, "Attempting forced close with sqlite3_close_v2\n");
                    sqlite3_close_v2(db);
                    fprintf(stderr, "Database connection force closed\n");
                    break;
                }
            } else {
                fprintf(stderr, "Error closing database: %s\n", sqlite3_errmsg(db));
                sqlite3_close_v2(db);
                fprintf(stderr, "Database connection force closed after error\n");
                break;
            }
        }
        
        db = NULL;
    }
}