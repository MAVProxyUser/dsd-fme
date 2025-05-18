#include <stdio.h>
#include <stdint.h>
#include <sqlite3.h>
#include <time.h>
#include "db_logger.h"

static sqlite3 *db = NULL;
static uint64_t current_h_mi = 0;
static uint32_t current_c_mi = 0;
static int current_context = 0; /* 1 = header, 2 = control */
static int current_slot = 0;
static uint32_t current_algid = 0;
static int current_superframe_id = 0;
static int frame_count_in_superframe = 0;

/* Initialize the database connection */
static void db_init(void) {
    if (!db) {
        char db_filename[256];
        time_t now = time(NULL);
        struct tm *tm_now = localtime(&now);
        snprintf(db_filename, sizeof(db_filename), "dmr_capture_%04d%02d%02d_%02d%02d%02d.db",
                 tm_now->tm_year + 1900, tm_now->tm_mon + 1, tm_now->tm_mday,
                 tm_now->tm_hour, tm_now->tm_min, tm_now->tm_sec);
        
        int rc = sqlite3_open(db_filename, &db);
        if (rc != SQLITE_OK) {
            fprintf(stderr, "db_logger: cannot open database %s: %s\n", db_filename, sqlite3_errmsg(db));
            sqlite3_close(db);
            db = NULL;
        } else {
            sqlite3_exec(db, "PRAGMA foreign_keys = ON;", NULL, NULL, NULL);
            fprintf(stderr, "db_logger: opened database %s\n", db_filename);
        }
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
        " superframe_id INTEGER"
        ");", tbl);
    sqlite3_exec(db, sql, NULL, NULL, &errmsg);
    if (errmsg) sqlite3_free(errmsg);
    sqlite3_free(sql);
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
        " superframe_id INTEGER"
        ");", tbl);
    sqlite3_exec(db, sql, NULL, NULL, &errmsg);
    if (errmsg) sqlite3_free(errmsg);
    sqlite3_free(sql);
}

void db_log_ambe(uint64_t ambe) {
    db_init();
    if (!db) return;
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
        
        /* Create the unencrypted table if it doesn't exist */
        char *sql = sqlite3_mprintf(
            "CREATE TABLE IF NOT EXISTS '%q' ("
            " id INTEGER PRIMARY KEY,"
            " ambe_hex TEXT,"
            " timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,"
            " mi_full INTEGER,"
            " algid INTEGER,"
            " slot INTEGER,"
            " superframe_id INTEGER"
            ");", tbl);
        sqlite3_exec(db, sql, NULL, NULL, NULL);
        sqlite3_free(sql);
    }
    
    char ambe_hex[17];
    snprintf(ambe_hex, sizeof(ambe_hex), "%016llX", (unsigned long long)ambe);
    
    char *errmsg = NULL;
    char *sql = sqlite3_mprintf(
        "INSERT INTO '%q' (ambe_hex, mi_full, algid, slot, superframe_id) VALUES ('%q', %llu, %u, %d, %d);",
        tbl, ambe_hex, (unsigned long long)current_mi, current_algid, current_slot, current_superframe_id);
    
    int rc = sqlite3_exec(db, sql, NULL, NULL, &errmsg);
    if (rc != SQLITE_OK) {
        fprintf(stderr, "db_logger: failed to insert AMBE: %s\n", errmsg);
        sqlite3_free(errmsg);
    }
    
    sqlite3_free(sql);
    
    /* Create correlation table if it doesn't exist */
    sql = sqlite3_mprintf(
        "CREATE TABLE IF NOT EXISTS dmr_correlations ("
        " id INTEGER PRIMARY KEY,"
        " header_mi INTEGER,"
        " control_mi INTEGER,"
        " slot INTEGER,"
        " algid INTEGER,"
        " timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,"
        " UNIQUE(header_mi, control_mi, slot)"
        ");");
    sqlite3_exec(db, sql, NULL, NULL, NULL);
    sqlite3_free(sql);
    
    /* Insert correlation if we have both MIs */
    if (current_h_mi != 0 && current_c_mi != 0) {
        sql = sqlite3_mprintf(
            "INSERT OR IGNORE INTO dmr_correlations (header_mi, control_mi, slot, algid) "
            "VALUES (%llu, %u, %d, %u);",
            (unsigned long long)current_h_mi, current_c_mi, current_slot, current_algid);
        sqlite3_exec(db, sql, NULL, NULL, NULL);
        sqlite3_free(sql);
    }
    
    /* Increment frame count for the superframe */
    if (current_superframe_id > 0) {
        frame_count_in_superframe++;
    }
}

void db_start_superframe(int slot, int color_code, const char *sync_type) {
    db_init();
    if (!db) return;
    
    /* Create superframes table if needed */
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
        " crc_passed INTEGER DEFAULT 1"
        ");");
    sqlite3_exec(db, sql, NULL, NULL, NULL);
    sqlite3_free(sql);
    
    /* Insert new superframe */
    sql = sqlite3_mprintf(
        "INSERT INTO superframes (slot, color_code, sync_type, h_mi, c_mi) "
        "VALUES (%d, %d, '%q', %llu, %u);",
        slot, color_code, sync_type, (unsigned long long)current_h_mi, current_c_mi);
    sqlite3_exec(db, sql, NULL, NULL, NULL);
    sqlite3_free(sql);
    
    current_superframe_id = (int)sqlite3_last_insert_rowid(db);
    frame_count_in_superframe = 0;
    
    /* Update AMBE tables to include superframe_id column */
    char tbl[64];
    if (current_context == 1 && current_h_mi != 0) {
        snprintf(tbl, sizeof(tbl), "H_%08X_S%d", (uint32_t)(current_h_mi & 0xFFFFFFFF), current_slot);
    } else if (current_context == 2 && current_c_mi != 0) {
        snprintf(tbl, sizeof(tbl), "C_%08X_S%d", current_c_mi, current_slot);
    } else {
        snprintf(tbl, sizeof(tbl), "U_00000000_S%d", current_slot);
    }
    
    sql = sqlite3_mprintf(
        "ALTER TABLE '%q' ADD COLUMN superframe_id INTEGER DEFAULT NULL;",
        tbl);
    sqlite3_exec(db, sql, NULL, NULL, NULL);
    sqlite3_free(sql);
}

void db_end_superframe(void) {
    if (!db || current_superframe_id == 0) return;
    
    /* Update frame count */
    char *sql = sqlite3_mprintf(
        "UPDATE superframes SET frame_count = %d WHERE id = %d;",
        frame_count_in_superframe, current_superframe_id);
    sqlite3_exec(db, sql, NULL, NULL, NULL);
    sqlite3_free(sql);
    
    current_superframe_id = 0;
    frame_count_in_superframe = 0;
}

void db_set_radio_ids(uint32_t source, uint32_t target) {
    db_init();
    if (!db) return;
    if (current_superframe_id == 0) return;
    
    char *sql = sqlite3_mprintf(
        "UPDATE superframes SET source_id = %u, target_id = %u WHERE id = %d;",
        source, target, current_superframe_id);
    
    char *errmsg = NULL;
    int rc = sqlite3_exec(db, sql, NULL, NULL, &errmsg);
    if (rc != SQLITE_OK) {
        fprintf(stderr, "db_logger: failed to update radio IDs: %s\n", errmsg);
        sqlite3_free(errmsg);
    }
    
    sqlite3_free(sql);
}

void db_set_flco_metadata(uint8_t flco, uint8_t fid, uint8_t so, const char *manufacturer) {
    db_init();
    if (!db) return;
    if (current_superframe_id == 0) return;
    
    char *sql = sqlite3_mprintf(
        "UPDATE superframes SET flco = %u, fid = %u, service_options = %u, manufacturer = '%q' WHERE id = %d;",
        flco, fid, so, manufacturer ? manufacturer : "", current_superframe_id);
    
    char *errmsg = NULL;
    int rc = sqlite3_exec(db, sql, NULL, NULL, &errmsg);
    if (rc != SQLITE_OK) {
        fprintf(stderr, "db_logger: failed to update FLCO metadata: %s\n", errmsg);
        sqlite3_free(errmsg);
    }
    
    sqlite3_free(sql);
}

void db_set_call_flags(int group_call, int priority_call, int emergency_call, int encrypted) {
    db_init();
    if (!db) return;
    if (current_superframe_id == 0) return;
    
    char *sql = sqlite3_mprintf(
        "UPDATE superframes SET group_call = %d, priority_call = %d, emergency_call = %d, encrypted = %d WHERE id = %d;",
        group_call, priority_call, emergency_call, encrypted, current_superframe_id);
    
    char *errmsg = NULL;
    int rc = sqlite3_exec(db, sql, NULL, NULL, &errmsg);
    if (rc != SQLITE_OK) {
        fprintf(stderr, "db_logger: failed to update call flags: %s\n", errmsg);
        sqlite3_free(errmsg);
    }
    
    sqlite3_free(sql);
}

void db_set_privacy_info(uint32_t algid, int data_format) {
    db_init();
    if (!db) return;
    if (current_superframe_id == 0) return;
    
    char *sql = sqlite3_mprintf(
        "UPDATE superframes SET privacy_algid = %u, data_format = %d WHERE id = %d;",
        algid, data_format, current_superframe_id);
    
    char *errmsg = NULL;
    int rc = sqlite3_exec(db, sql, NULL, NULL, &errmsg);
    if (rc != SQLITE_OK) {
        fprintf(stderr, "db_logger: failed to update privacy info: %s\n", errmsg);
        sqlite3_free(errmsg);
    }
    
    sqlite3_free(sql);
}

void db_set_crc_status(int crc_passed) {
    db_init();
    if (!db) return;
    if (current_superframe_id == 0) return;
    
    char *sql = sqlite3_mprintf(
        "UPDATE superframes SET crc_passed = %d WHERE id = %d;",
        crc_passed, current_superframe_id);
    
    char *errmsg = NULL;
    int rc = sqlite3_exec(db, sql, NULL, NULL, &errmsg);
    if (rc != SQLITE_OK) {
        fprintf(stderr, "db_logger: failed to update CRC status: %s\n", errmsg);
        sqlite3_free(errmsg);
    }
    
    sqlite3_free(sql);
}

void db_set_talkgroup(uint32_t talkgroup) {
    db_init();
    if (!db) return;
    
    /* Create metadata table if needed */
    char *sql = sqlite3_mprintf(
        "CREATE TABLE IF NOT EXISTS dmr_metadata ("
        " id INTEGER PRIMARY KEY,"
        " talkgroup INTEGER,"
        " superframe_id INTEGER,"
        " timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,"
        " FOREIGN KEY(superframe_id) REFERENCES superframes(id)"
        ");");
    sqlite3_exec(db, sql, NULL, NULL, NULL);
    sqlite3_free(sql);
    
    /* Insert talkgroup entry */
    sql = sqlite3_mprintf(
        "INSERT INTO dmr_metadata (talkgroup, superframe_id) VALUES (%u, %d);",
        talkgroup, current_superframe_id);
    
    char *errmsg = NULL;
    int rc = sqlite3_exec(db, sql, NULL, NULL, &errmsg);
    if (rc != SQLITE_OK) {
        fprintf(stderr, "db_logger: failed to insert talkgroup: %s\n", errmsg);
        sqlite3_free(errmsg);
    }
    
    sqlite3_free(sql);
}

void db_update_encrypted_flag(void) {
    db_init();
    if (!db) return;
    if (current_superframe_id == 0) return;
    
    char *sql = sqlite3_mprintf(
        "UPDATE superframes SET encrypted = 1 WHERE id = %d;",
        current_superframe_id);
    
    char *errmsg = NULL;
    int rc = sqlite3_exec(db, sql, NULL, NULL, &errmsg);
    if (rc != SQLITE_OK) {
        fprintf(stderr, "db_logger: failed to update encrypted flag: %s\n", errmsg);
        sqlite3_free(errmsg);
    }
    
    sqlite3_free(sql);
}

void db_close(void) {
    if (db) {
        db_end_superframe(); /* Close any open superframe */
        sqlite3_close(db);
        db = NULL;
    }
}