/*
 * moneywiz-snapshot: copy one MoneyWiz SQLite database to one fixed location.
 *
 * This is the only component of the least-privilege setup that holds Full
 * Disk Access. launchd runs it directly (no shell in between), so macOS
 * attributes the read of MoneyWiz's protected container to this binary alone,
 * and the MCP server and Claude Desktop need no extra permissions.
 *
 * The grant cannot be repurposed to read other files:
 *   - both paths are fixed at compile time; the program accepts no arguments
 *     and reads no configuration or environment input;
 *   - the source is opened read-only and must not be a symlink, so a link
 *     planted in place of the database cannot redirect the copy elsewhere;
 *   - the destination directory must be a real, owner-only directory.
 *
 * The copy uses SQLite's online backup API, which includes changes still in
 * the source's -wal file, then switches the copy to rollback-journal mode so
 * it is a single self-contained file. It is verified with PRAGMA quick_check
 * and moved into place with an atomic rename, so readers never see a partial
 * snapshot.
 */

#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <sqlite3.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>

#ifndef SNAPSHOT_SOURCE
#error "SNAPSHOT_SOURCE (absolute path of the MoneyWiz database) must be defined"
#endif
#ifndef SNAPSHOT_DEST_DIR
#error "SNAPSHOT_DEST_DIR (absolute path of the snapshot directory) must be defined"
#endif

#define SNAPSHOT_NAME "snapshot.sqlite"
#define BUSY_RETRIES 40     /* x 250 ms = 10 s while MoneyWiz holds a lock */
#define BUSY_SLEEP_MS 250

__attribute__((format(printf, 2, 3)))
static void log_msg(const char *level, const char *fmt, ...) {
    char stamp[32];
    time_t now = time(NULL);
    struct tm tm_now;
    localtime_r(&now, &tm_now);
    strftime(stamp, sizeof stamp, "%Y-%m-%dT%H:%M:%S%z", &tm_now);

    fprintf(stderr, "%s moneywiz-snapshot %s: ", stamp, level);
    va_list args;
    va_start(args, fmt);
    vfprintf(stderr, fmt, args);
    va_end(args);
    fputc('\n', stderr);
}

/* Create the snapshot directory as 0700, or verify an existing one is safe. */
static int ensure_private_dir(const char *dir) {
    struct stat st;
    if (lstat(dir, &st) == 0) {
        if (!S_ISDIR(st.st_mode)) {
            log_msg("error", "%s exists but is not a directory (symlinks are refused)", dir);
            return -1;
        }
        if (st.st_uid != getuid()) {
            log_msg("error", "%s is not owned by the current user", dir);
            return -1;
        }
        if ((st.st_mode & 077) != 0 && chmod(dir, 0700) != 0) {
            log_msg("error", "cannot restrict permissions on %s: %s", dir, strerror(errno));
            return -1;
        }
        return 0;
    }
    if (errno != ENOENT) {
        log_msg("error", "cannot inspect %s: %s", dir, strerror(errno));
        return -1;
    }
    if (mkdir(dir, 0700) != 0) {
        log_msg("error", "cannot create %s: %s", dir, strerror(errno));
        return -1;
    }
    return 0;
}

static int quick_check_ok(sqlite3 *db) {
    sqlite3_stmt *stmt = NULL;
    int ok = 0;
    if (sqlite3_prepare_v2(db, "PRAGMA quick_check", -1, &stmt, NULL) == SQLITE_OK &&
        sqlite3_step(stmt) == SQLITE_ROW) {
        const unsigned char *result = sqlite3_column_text(stmt, 0);
        ok = result != NULL && strcmp((const char *)result, "ok") == 0;
    }
    sqlite3_finalize(stmt);
    return ok;
}

/*
 * 1 if SNAPSHOT_SOURCE + suffix exists (size in *size), 0 if absent, -1 on
 * error. Symlinks are refused: SQLITE_OPEN_NOFOLLOW only covers the main
 * database file, not the -wal/-shm/-journal files SQLite opens alongside it.
 */
static int side_file_state(const char *suffix, off_t *size) {
    char path[PATH_MAX];
    struct stat st;
    *size = 0;
    if (snprintf(path, sizeof path, "%s%s", SNAPSHOT_SOURCE, suffix) >= (int)sizeof path) {
        return -1;
    }
    if (lstat(path, &st) == 0) {
        if (S_ISLNK(st.st_mode)) {
            log_msg("error", "refusing symlinked side file %s", path);
            return -1;
        }
        *size = st.st_size;
        return 1;
    }
    if (errno != ENOENT) {
        log_msg("error", "cannot inspect %s: %s", path, strerror(errno));
        return -1;
    }
    return 0;
}

/* Build "file:<percent-encoded source path>?immutable=1". Returns 0 on success. */
static int immutable_uri(char *out, size_t out_size) {
    static const char hex[] = "0123456789ABCDEF";
    static const char suffix[] = "?immutable=1";
    size_t n = 0;
    if (out_size < 6) {
        return -1;
    }
    memcpy(out, "file:", 5);
    n = 5;
    for (const unsigned char *p = (const unsigned char *)SNAPSHOT_SOURCE; *p != '\0'; p++) {
        int plain = (*p >= 'A' && *p <= 'Z') || (*p >= 'a' && *p <= 'z') ||
                    (*p >= '0' && *p <= '9') || *p == '-' || *p == '.' || *p == '_' ||
                    *p == '~' || *p == '/';
        if (n + (plain ? 1 : 3) >= out_size) {
            return -1;
        }
        if (plain) {
            out[n++] = (char)*p;
        } else {
            out[n++] = '%';
            out[n++] = hex[*p >> 4];
            out[n++] = hex[*p & 0x0F];
        }
    }
    if (n + sizeof suffix > out_size) {
        return -1;
    }
    memcpy(out + n, suffix, sizeof suffix);
    return 0;
}

static int same_file_state(const struct stat *a, const struct stat *b) {
    return a->st_dev == b->st_dev && a->st_ino == b->st_ino && a->st_size == b->st_size &&
           a->st_mtimespec.tv_sec == b->st_mtimespec.tv_sec &&
           a->st_mtimespec.tv_nsec == b->st_mtimespec.tv_nsec;
}

/*
 * Back up the source into tmp_path. Returns 0 on success.
 *
 * A read-only connection cannot open a WAL-mode database whose -shm file is
 * missing, which is the normal state while MoneyWiz is closed. In that case
 * every committed change is already in the main file, so it is read in
 * immutable mode and the copy is rejected if the file changed meanwhile.
 */
static int copy_database(const char *tmp_path) {
    sqlite3 *src = NULL;
    sqlite3 *dst = NULL;
    sqlite3_backup *backup = NULL;
    int status = -1;
    int rc;

    off_t shm_size, wal_size, journal_size;
    int shm = side_file_state("-shm", &shm_size);
    int wal = side_file_state("-wal", &wal_size);
    int journal = side_file_state("-journal", &journal_size);
    if (shm < 0 || wal < 0 || journal < 0) {
        return -1;
    }

    const char *open_name = SNAPSHOT_SOURCE;
    int open_flags = SQLITE_OPEN_READONLY | SQLITE_OPEN_NOFOLLOW;
    char uri[PATH_MAX * 3 + 32];
    struct stat before;
    int immutable = 0;

    if (shm == 0) {
        if (wal_size > 0 || journal_size > 0) {
            log_msg("error",
                    "source has an unrecovered journal or write-ahead log; "
                    "open MoneyWiz once so it can recover, then the next run will succeed");
            return -1;
        }
        if (immutable_uri(uri, sizeof uri) != 0) {
            log_msg("error", "source path is too long");
            return -1;
        }
        if (lstat(SNAPSHOT_SOURCE, &before) != 0) {
            log_msg("error", "cannot open source database: %s", strerror(errno));
            return -1;
        }
        open_name = uri;
        open_flags |= SQLITE_OPEN_URI;
        immutable = 1;
    }

    rc = sqlite3_open_v2(open_name, &src, open_flags, NULL);
    if (rc != SQLITE_OK) {
        log_msg("error", "cannot open source database: %s", src ? sqlite3_errmsg(src) : "out of memory");
        goto done;
    }
    sqlite3_busy_timeout(src, BUSY_RETRIES * BUSY_SLEEP_MS);

    rc = sqlite3_open_v2(tmp_path, &dst, SQLITE_OPEN_READWRITE | SQLITE_OPEN_NOFOLLOW, NULL);
    if (rc != SQLITE_OK) {
        log_msg("error", "cannot open temporary snapshot: %s", dst ? sqlite3_errmsg(dst) : "out of memory");
        goto done;
    }

    backup = sqlite3_backup_init(dst, "main", src, "main");
    if (backup == NULL) {
        log_msg("error", "cannot start backup: %s", sqlite3_errmsg(dst));
        goto done;
    }
    for (int attempt = 0;; attempt++) {
        rc = sqlite3_backup_step(backup, -1);
        if (rc == SQLITE_DONE) {
            break;
        }
        if ((rc == SQLITE_BUSY || rc == SQLITE_LOCKED) && attempt < BUSY_RETRIES) {
            sqlite3_sleep(BUSY_SLEEP_MS);
            continue;
        }
        log_msg("error", "backup failed: %s", sqlite3_errstr(rc));
        goto done;
    }
    rc = sqlite3_backup_finish(backup);
    backup = NULL;
    if (rc != SQLITE_OK) {
        log_msg("error", "backup did not complete: %s", sqlite3_errmsg(dst));
        goto done;
    }
    if (immutable) {
        /* Immutable reads take no locks: discard the copy if anything wrote
         * to the main file while it was being read. */
        struct stat after;
        if (lstat(SNAPSHOT_SOURCE, &after) != 0 || !same_file_state(&before, &after)) {
            log_msg("error", "source changed during the copy; the next run will retry");
            goto done;
        }
    }

    /* A single self-contained file: readers need no -wal/-shm companions. */
    if (sqlite3_exec(dst, "PRAGMA journal_mode=DELETE", NULL, NULL, NULL) != SQLITE_OK) {
        log_msg("error", "cannot convert snapshot journal mode: %s", sqlite3_errmsg(dst));
        goto done;
    }
    if (!quick_check_ok(dst)) {
        log_msg("error", "snapshot failed integrity check");
        goto done;
    }
    status = 0;

done:
    if (backup != NULL) {
        sqlite3_backup_finish(backup);
    }
    if (dst != NULL && sqlite3_close(dst) != SQLITE_OK) {
        log_msg("error", "cannot close snapshot cleanly: %s", sqlite3_errmsg(dst));
        status = -1;
    }
    /* Read-only with no open statements, so a failed close cannot lose data;
     * log it anyway so a leaked handle is visible. */
    if (src != NULL && sqlite3_close(src) != SQLITE_OK) {
        log_msg("warning", "cannot close source database cleanly: %s", sqlite3_errmsg(src));
    }
    return status;
}

/*
 * Remove the temporary copy's SQLite side files. The backup briefly opens the
 * copy in WAL mode (the flag comes from the source header), and macOS's SQLite
 * can leave the -shm behind after switching to rollback mode and closing.
 */
static void remove_side_files(const char *db_path) {
    static const char *const suffixes[] = {"-wal", "-shm", "-journal"};
    char side[PATH_MAX];
    for (size_t i = 0; i < sizeof suffixes / sizeof suffixes[0]; i++) {
        if (snprintf(side, sizeof side, "%s%s", db_path, suffixes[i]) < (int)sizeof side) {
            unlink(side);
        }
    }
}

static int full_fsync(const char *path, int flags) {
    int fd = open(path, flags | O_NOFOLLOW);
    if (fd < 0) {
        return -1;
    }
    /* F_FULLFSYNC asks the drive to flush its cache; fall back to fsync. */
    int rc = fcntl(fd, F_FULLFSYNC);
    if (rc != 0) {
        rc = fsync(fd);
    }
    int saved_errno = errno; /* close() must not mask the flush error */
    close(fd);
    errno = saved_errno;
    return rc;
}

int main(int argc, char **argv) {
    (void)argv;
    if (argc != 1) {
        fprintf(stderr, "moneywiz-snapshot takes no arguments; its paths are fixed at build time\n");
        return 2;
    }
    umask(077);

    char final_path[PATH_MAX];
    char tmp_path[PATH_MAX];
    if (snprintf(final_path, sizeof final_path, "%s/%s", SNAPSHOT_DEST_DIR, SNAPSHOT_NAME) >= (int)sizeof final_path ||
        snprintf(tmp_path, sizeof tmp_path, "%s/.%s.XXXXXX", SNAPSHOT_DEST_DIR, SNAPSHOT_NAME) >= (int)sizeof tmp_path) {
        log_msg("error", "snapshot path is too long");
        return 1;
    }

    if (ensure_private_dir(SNAPSHOT_DEST_DIR) != 0) {
        return 1;
    }

    int tmp_fd = mkstemp(tmp_path);
    if (tmp_fd < 0) {
        log_msg("error", "cannot create temporary file: %s", strerror(errno));
        return 1;
    }
    close(tmp_fd);

    int copied = copy_database(tmp_path);
    remove_side_files(tmp_path);
    if (copied != 0 || full_fsync(tmp_path, O_RDONLY) != 0) {
        unlink(tmp_path);
        return 1;
    }
    if (rename(tmp_path, final_path) != 0) {
        log_msg("error", "cannot move snapshot into place: %s", strerror(errno));
        unlink(tmp_path);
        return 1;
    }
    if (full_fsync(SNAPSHOT_DEST_DIR, O_RDONLY | O_DIRECTORY) != 0) {
        log_msg("warning", "snapshot is in place but its directory could not be flushed: %s",
                strerror(errno));
    }

    struct stat st;
    if (stat(final_path, &st) == 0) {
        log_msg("info", "snapshot updated (%lld bytes)", (long long)st.st_size);
    }
    return 0;
}
