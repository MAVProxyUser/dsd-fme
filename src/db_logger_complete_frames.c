/*
 * Modified database logger to capture complete DMR voice frames
 * This captures all 3 AMBE frames per burst for proper cryptanalysis
 */

#include <stdio.h>
#include <sqlite3.h>
#include <time.h>
#include <sys/time.h>
#include <string.h>
#include <stdint.h>
#include "dsd.h"
#include "sqlite_logger.h"

// Extended schema with complete frame logging
static const char* sql_create_complete_frames = 
    "CREATE TABLE IF NOT EXISTS CompleteFrames ("
    "    id INTEGER PRIMARY KEY AUTOINCREMENT,"
    "    superframe_id INTEGER,"
    "    timestamp REAL,"
    "    slot INTEGER,"
    "    burst_num INTEGER,"      // Which burst in superframe
    "    ambe1 BLOB,"           // First AMBE frame (64-bit)
    "    ambe2 BLOB,"           // Second AMBE frame
    "    ambe3 BLOB,"           // Third AMBE frame
    "    mi INTEGER,"           // Message Indicator (IV)
    "    algid INTEGER,"        // Algorithm ID
    "    key_id INTEGER,"       // Key ID
    "    src_id INTEGER,"       // Source radio ID
    "    dst_id INTEGER,"       // Destination ID
    "    encrypted INTEGER,"    // Encryption flag
    "    errors INTEGER,"       // Error count
    "    FOREIGN KEY(superframe_id) REFERENCES Superframes(id)"
    ");";

// Global to accumulate AMBE frames
typedef struct {
    uint64_t ambe[3];        // 3 AMBE frames
    int frame_count;         // How many collected
    uint32_t current_mi;     // Current MI
    int current_slot;        // Current slot
    int burst_number;        // Burst number in superframe
} voice_frame_accumulator_t;

static voice_frame_accumulator_t frame_accumulator[2] = {0}; // One per slot

// Modified function to log complete frames
void db_log_complete_frame(int slot) {
    if (!db || !in_superframe) return;
    
    voice_frame_accumulator_t *acc = &frame_accumulator[slot];
    
    // Only log when we have all 3 frames
    if (acc->frame_count != 3) return;
    
    const char* sql = "INSERT INTO CompleteFrames "
                      "(superframe_id, timestamp, slot, burst_num, "
                      "ambe1, ambe2, ambe3, mi, algid, key_id, "
                      "src_id, dst_id, encrypted, errors) "
                      "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)";
    
    sqlite3_stmt* stmt;
    if (sqlite3_prepare_v2(db, sql, -1, &stmt, NULL) != SQLITE_OK) {
        fprintf(stderr, "Failed to prepare complete frame statement: %s\n", 
                sqlite3_errmsg(db));
        return;
    }
    
    // Get current time
    struct timeval tv;
    gettimeofday(&tv, NULL);
    double timestamp = tv.tv_sec + tv.tv_usec / 1e6;
    
    // Bind parameters
    sqlite3_bind_int64(stmt, 1, current_superframe_id);
    sqlite3_bind_double(stmt, 2, timestamp);
    sqlite3_bind_int(stmt, 3, slot);
    sqlite3_bind_int(stmt, 4, acc->burst_number);
    sqlite3_bind_blob(stmt, 5, &acc->ambe[0], sizeof(uint64_t), SQLITE_STATIC);
    sqlite3_bind_blob(stmt, 6, &acc->ambe[1], sizeof(uint64_t), SQLITE_STATIC);
    sqlite3_bind_blob(stmt, 7, &acc->ambe[2], sizeof(uint64_t), SQLITE_STATIC);
    sqlite3_bind_int64(stmt, 8, acc->current_mi);
    sqlite3_bind_int(stmt, 9, current_algid);
    sqlite3_bind_int(stmt, 10, current_key_id);
    sqlite3_bind_int(stmt, 11, current_src_id);
    sqlite3_bind_int(stmt, 12, current_dst_id);
    sqlite3_bind_int(stmt, 13, is_encrypted);
    sqlite3_bind_int(stmt, 14, total_errors);
    
    if (sqlite3_step(stmt) != SQLITE_DONE) {
        fprintf(stderr, "Failed to insert complete frame: %s\n", 
                sqlite3_errmsg(db));
    }
    
    sqlite3_finalize(stmt);
    
    // Reset accumulator
    acc->frame_count = 0;
    acc->current_mi = 0;
    memset(acc->ambe, 0, sizeof(acc->ambe));
}

// Modified AMBE logging to accumulate frames
void db_log_ambe_accumulate(uint64_t ambe_hex, int slot, int frame_pos) {
    if (!db || !in_superframe) return;
    
    voice_frame_accumulator_t *acc = &frame_accumulator[slot];
    
    // Store the frame at correct position
    if (frame_pos >= 0 && frame_pos < 3) {
        acc->ambe[frame_pos] = ambe_hex;
        acc->frame_count++;
        acc->current_slot = slot;
        acc->current_mi = get_current_mi();
        acc->burst_number = get_burst_number();
        
        // If we have all 3 frames, log the complete frame
        if (acc->frame_count == 3) {
            db_log_complete_frame(slot);
        }
    }
    
    // Also log individual frame for backward compatibility
    db_log_ambe(ambe_hex);
}

// Hook into DMR voice frame processing
void process_dmr_voice_burst(dsd_opts *opts, dsd_state *state, 
                           char ambe_fr[4][24], char ambe_fr2[4][24], 
                           char ambe_fr3[4][24]) {
    
    int slot = state->currentslot;
    
    // Convert each AMBE frame to 64-bit value
    uint64_t ambe1 = 0, ambe2 = 0, ambe3 = 0;
    
    // Frame 1
    for (int i = 0; i < 4; i++) {
        for (int j = 0; j < 24; j++) {
            if (i * 24 + j < 64) {
                ambe1 = (ambe1 << 1) | (ambe_fr[i][j] & 1);
            }
        }
    }
    
    // Frame 2
    for (int i = 0; i < 4; i++) {
        for (int j = 0; j < 24; j++) {
            if (i * 24 + j < 64) {
                ambe2 = (ambe2 << 1) | (ambe_fr2[i][j] & 1);
            }
        }
    }
    
    // Frame 3
    for (int i = 0; i < 4; i++) {
        for (int j = 0; j < 24; j++) {
            if (i * 24 + j < 64) {
                ambe3 = (ambe3 << 1) | (ambe_fr3[i][j] & 1);
            }
        }
    }
    
    // Log all 3 frames
    db_log_ambe_accumulate(ambe1, slot, 0);
    db_log_ambe_accumulate(ambe2, slot, 1);
    db_log_ambe_accumulate(ambe3, slot, 2);
}

// Create the new table
int db_init_complete_frames() {
    if (!db) return -1;
    
    char *err_msg = NULL;
    if (sqlite3_exec(db, sql_create_complete_frames, NULL, NULL, &err_msg) != SQLITE_OK) {
        fprintf(stderr, "Failed to create CompleteFrames table: %s\n", err_msg);
        sqlite3_free(err_msg);
        return -1;
    }
    
    return 0;
}

// Query complete frames for analysis
sqlite3_stmt* db_query_complete_frames_by_mi(uint64_t mi) {
    const char* sql = "SELECT * FROM CompleteFrames WHERE mi = ? ORDER BY id";
    
    sqlite3_stmt* stmt;
    if (sqlite3_prepare_v2(db, sql, -1, &stmt, NULL) != SQLITE_OK) {
        fprintf(stderr, "Failed to prepare query: %s\n", sqlite3_errmsg(db));
        return NULL;
    }
    
    sqlite3_bind_int64(stmt, 1, mi);
    return stmt;
}