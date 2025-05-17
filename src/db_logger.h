#ifndef DB_LOGGER_H
#define DB_LOGGER_H

#include <stdint.h>

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

/* Close the database connection (call on program exit) */
void db_close(void);

#endif /* DB_LOGGER_H */