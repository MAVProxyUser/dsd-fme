#ifndef SQLITE_LOGGER_H
#define SQLITE_LOGGER_H

#include <sqlite3.h>

/* Initialize the SQLite database for logging DMR frames. */
void init_sqlite_logger(void);

/* Log a header (H-) frame: timestamp + raw hex payload. */
void log_HFrame(unsigned long timestamp, const char *hex_payload);

/* Log a control (C-) frame: timestamp + raw hex payload. */
void log_CFrame(unsigned long timestamp, const char *hex_payload);

/* Log an AMBE voice frame: timestamp + raw hex payload. */
void log_AMBEFrame(unsigned long timestamp, const char *hex_payload);

