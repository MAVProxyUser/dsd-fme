#ifndef DB_LOGGER_H
#define DB_LOGGER_H

#include <stdint.h>
#include <sqlite3.h>

/* Initialize the database system with triggers for auto correlation */
void db_init_with_triggers(void);

/* Archive the current database and create a fresh one */
void db_archive_and_create_new(void);

/* Set the current Header (H-) MI value for subsequent AMBE logging */
void db_set_header_mi(uint64_t mi, int slot, uint32_t algid);

/* Set the current Control (C-) MI value for subsequent AMBE logging */
void db_set_control_mi(uint32_t mi);

/* Log an AMBE frame to the appropriate table based on current context */
void db_log_ambe(uint64_t ambe);

/* Start a new superframe */
void db_start_superframe(int slot, int color_code, const char *sync_type);

/* End the current superframe */
void db_end_superframe(void);

/* Set radio IDs for the current superframe */
void db_set_radio_ids(uint32_t source, uint32_t target);

/* Set FLCO metadata for the current superframe */
void db_set_flco_metadata(uint8_t flco, uint8_t fid, uint8_t so, const char *manufacturer);

/* Set call type flags for the current superframe */
void db_set_call_flags(int group_call, int priority_call, int emergency_call, int encrypted);

/* Set privacy/encryption info for the current superframe */
void db_set_privacy_info(uint32_t algid, int data_format);

/* Set CRC status for the current superframe */
void db_set_crc_status(int crc_passed);

/* Set talkgroup for metadata table */
void db_set_talkgroup(uint32_t talkgroup);

/* Update encrypted flag when MI is detected */
void db_update_encrypted_flag(void);

/* Fix encrypted flags for all superframes in the database */
void db_fix_encrypted_flags(void);

/* Consolidate current database with master database */
void db_consolidate_with_master(void);

/* Register custom SQLite functions */
void db_register_lfsr_functions(sqlite3 *db);

/* Close the database connection (call on program exit) */
void db_close(void);

#endif /* DB_LOGGER_H */