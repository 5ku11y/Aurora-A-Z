#ifndef SPELUNKR360_SCHEDULE_CORE_H
#define SPELUNKR360_SCHEDULE_CORE_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define SP_MAX_ITEMS 96
#define SP_MAX_BUMPS 192
#define SP_MAX_SLIDES 16
#define SP_ID_BYTES 192
#define SP_TITLE_BYTES 256
#define SP_FILE_BYTES 320
#define SP_PATH_BYTES 256
#define SP_URL_BYTES 1024
#define SP_KEY_BYTES 2048
#define SP_MAX_ENTRIES (SP_MAX_ITEMS * 2 + 8)

enum sp_segment_kind {
    SP_SEGMENT_NONE = 0,
    SP_SEGMENT_SHOW = 1,
    SP_SEGMENT_BUMP = 2,
};

struct sp_pointer {
    int version;
    int64_t epoch_ms;
    int64_t effective_ms;
    int start_index;
    char manifest[SP_PATH_BYTES];
};

struct sp_item {
    char id[SP_ID_BYTES];
    char mp4[SP_FILE_BYTES];
    char title[SP_TITLE_BYTES];
    char year[24];
    int duration_s;
    int in_s;
    bool off_air;
};

struct sp_bump {
    char id[SP_ID_BYTES];
    bool active;
    bool has_date_range;
    char date_start[20];
    char date_end[20];
    int slide_count;
    int slide_ms[SP_MAX_SLIDES];
};

struct sp_schedule {
    int engine;
    int version;
    char channel[64];
    char platform_path[SP_PATH_BYTES];

    int item_count;
    struct sp_item items[SP_MAX_ITEMS];

    int channel_bump_count;
    struct sp_bump channel_bumps[SP_MAX_BUMPS];

    int platform_bump_count;
    struct sp_bump platform_bumps[SP_MAX_BUMPS];

    bool has_block;
    bool has_ads;
};

struct sp_deck_state {
    int order[SP_MAX_BUMPS];
    int order_count;
    int pos;
    char key[SP_KEY_BYTES];
    int recent[SP_MAX_BUMPS * 2];
    int recent_count;
    int rounds;
};

struct sp_cycle_entry {
    enum sp_segment_kind kind;
    int64_t off_ms;
    int64_t duration_ms;
    int item_index;
    int channel_bump_index;
    int platform_bump_index;
};

struct sp_cycle {
    int cycle_index;
    int64_t start_ms;
    int64_t length_ms;
    int entry_count;
    struct sp_cycle_entry entries[SP_MAX_ENTRIES];
};

struct sp_now {
    bool ok;
    enum sp_segment_kind kind;
    int version;
    int cycle;
    int entry_index;
    int item_index;
    int64_t now_ms;
    int64_t segment_start_ms;
    int64_t segment_length_ms;
    int64_t offset_ms;
    int64_t remaining_ms;
    char title[SP_TITLE_BYTES];
    char year[24];
    char id[SP_ID_BYTES];
    char mp4[SP_FILE_BYTES];
    char archive_url[SP_URL_BYTES];
    char channel_bump_id[SP_ID_BYTES];
    char platform_bump_id[SP_ID_BYTES];
};

int sp_parse_lineup_53(
    const char *json,
    size_t json_len,
    int64_t now_ms,
    struct sp_pointer *pointer,
    char *channel_name,
    size_t channel_name_size,
    char *channel_id,
    size_t channel_id_size,
    char *error,
    size_t error_size);

int sp_parse_manifest(
    const char *json,
    size_t json_len,
    struct sp_schedule *schedule,
    char *error,
    size_t error_size);

int sp_parse_platform(
    const char *json,
    size_t json_len,
    struct sp_schedule *schedule,
    char *error,
    size_t error_size);

int sp_find_now(
    const struct sp_schedule *schedule,
    const struct sp_pointer *pointer,
    int64_t now_ms,
    struct sp_now *out,
    char *error,
    size_t error_size);

const char *sp_segment_kind_name(enum sp_segment_kind kind);

#endif
