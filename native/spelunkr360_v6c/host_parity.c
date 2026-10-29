#include "schedule_core.h"
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static char *read_file(const char *path, size_t *size_out)
{
    FILE *fp = fopen(path, "rb");
    long size;
    char *data;
    if (fp == NULL) return NULL;
    if (fseek(fp, 0, SEEK_END) != 0) { fclose(fp); return NULL; }
    size = ftell(fp);
    if (size < 0 || fseek(fp, 0, SEEK_SET) != 0) { fclose(fp); return NULL; }
    data = malloc((size_t)size + 1u);
    if (data == NULL) { fclose(fp); return NULL; }
    if (fread(data, 1, (size_t)size, fp) != (size_t)size) { free(data); fclose(fp); return NULL; }
    fclose(fp);
    data[size] = '\0';
    *size_out = (size_t)size;
    return data;
}

static void adapt_platform_schema_marker(char *json)
{
    char *key;
    char *value;
    if (json == NULL) return;
    key = strstr(json, "\"engine\"");
    if (key == NULL) return;
    value = strchr(key, ':');
    if (value == NULL) return;
    value++;
    while (*value == ' ' || *value == '\t' || *value == '\r' || *value == '\n') value++;
    if (*value == '1') *value = '5';
}

static const char *kind_name(enum sp_segment_kind kind)
{
    if (kind == SP_SEGMENT_SHOW) return "show";
    if (kind == SP_SEGMENT_BUMP) return "bump";
    return "none";
}

int main(int argc, char **argv)
{
    char *lineup = NULL, *manifest = NULL, *platform = NULL;
    size_t lineup_size = 0, manifest_size = 0, platform_size = 0;
    int64_t now_ms;
    struct sp_pointer pointer;
    struct sp_schedule *schedule = NULL;
    struct sp_now now_result;
    char channel_name[64] = { 0 }, channel_id[64] = { 0 }, error[256] = { 0 };
    char bump_id[SP_ID_BYTES * 2 + 2] = { 0 };
    int rc = 1;

    if (argc != 5) {
        fprintf(stderr, "usage: %s lineup.json manifest.json platform.json now_ms\n", argv[0]);
        return 2;
    }
    now_ms = strtoll(argv[4], NULL, 10);
    lineup = read_file(argv[1], &lineup_size);
    manifest = read_file(argv[2], &manifest_size);
    platform = read_file(argv[3], &platform_size);
    schedule = calloc(1, sizeof(*schedule));
    if (lineup == NULL || manifest == NULL || platform == NULL || schedule == NULL) {
        fprintf(stderr, "input/allocation failure\n");
        goto done;
    }
    adapt_platform_schema_marker(platform);
    memset(&pointer, 0, sizeof(pointer));
    memset(&now_result, 0, sizeof(now_result));

    if (sp_parse_lineup_53(lineup, lineup_size, now_ms, &pointer,
            channel_name, sizeof(channel_name), channel_id, sizeof(channel_id), error, sizeof(error)) != 0) {
        fprintf(stderr, "lineup: %s\n", error); goto done;
    }
    if (sp_parse_manifest(manifest, manifest_size, schedule, error, sizeof(error)) != 0) {
        fprintf(stderr, "manifest: %s\n", error); goto done;
    }
    if (sp_parse_platform(platform, platform_size, schedule, error, sizeof(error)) != 0) {
        fprintf(stderr, "platform: %s\n", error); goto done;
    }
    if (sp_find_now(schedule, &pointer, now_ms, &now_result, error, sizeof(error)) != 0 || !now_result.ok) {
        fprintf(stderr, "find_now: %s\n", error); goto done;
    }

    if (now_result.kind == SP_SEGMENT_BUMP)
        snprintf(bump_id, sizeof(bump_id), "%s+%s", now_result.channel_bump_id, now_result.platform_bump_id);

    printf("kind=%s\n", kind_name(now_result.kind));
    printf("version=%d\n", now_result.version);
    printf("cycle=%d\n", now_result.cycle);
    printf("entry=%d\n", now_result.entry_index);
    printf("start=%" PRId64 "\n", now_result.segment_start_ms);
    printf("length=%" PRId64 "\n", now_result.segment_length_ms);
    printf("offset=%" PRId64 "\n", now_result.offset_ms);
    printf("id=%s\n", now_result.id);
    printf("title=%s\n", now_result.title);
    printf("url=%s\n", now_result.archive_url);
    printf("bumpid=%s\n", bump_id);
    rc = 0;

done:
    free(schedule); free(platform); free(manifest); free(lineup);
    return rc;
}
