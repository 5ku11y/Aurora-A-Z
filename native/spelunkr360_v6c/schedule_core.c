#define _POSIX_C_SOURCE 200809L
#include "schedule_core.h"

#include <ctype.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

/*
 * Tiny embedded JSON tokenizer derived from the public jsmn design.
 * Parent links are kept because Spelunkr's data is nested and we want
 * deterministic, allocation-bounded traversal on Xbox 360.
 */
typedef enum {
    JSMN_UNDEFINED = 0,
    JSMN_OBJECT = 1,
    JSMN_ARRAY = 2,
    JSMN_STRING = 3,
    JSMN_PRIMITIVE = 4
} jsmntype_t;

typedef struct {
    jsmntype_t type;
    int start;
    int end;
    int size;
    int parent;
} jsmntok_t;

typedef struct {
    unsigned int pos;
    unsigned int toknext;
    int toksuper;
} jsmn_parser;

enum {
    JSMN_ERROR_NOMEM = -1,
    JSMN_ERROR_INVAL = -2,
    JSMN_ERROR_PART = -3
};

static void jsmn_init(jsmn_parser *parser)
{
    parser->pos = 0;
    parser->toknext = 0;
    parser->toksuper = -1;
}

static jsmntok_t *jsmn_alloc_token(jsmn_parser *parser, jsmntok_t *tokens, size_t num_tokens)
{
    jsmntok_t *tok;
    if (parser->toknext >= num_tokens)
        return NULL;
    tok = &tokens[parser->toknext++];
    tok->start = -1;
    tok->end = -1;
    tok->size = 0;
    tok->parent = -1;
    tok->type = JSMN_UNDEFINED;
    return tok;
}

static void jsmn_fill_token(jsmntok_t *token, jsmntype_t type, int start, int end)
{
    token->type = type;
    token->start = start;
    token->end = end;
    token->size = 0;
}

static int jsmn_parse_primitive(
    jsmn_parser *parser,
    const char *js,
    size_t len,
    jsmntok_t *tokens,
    size_t num_tokens)
{
    const unsigned int start = parser->pos;
    jsmntok_t *token;

    for (; parser->pos < len; parser->pos++) {
        const char c = js[parser->pos];
        switch (c) {
        case '\t':
        case '\r':
        case '\n':
        case ' ':
        case ',':
        case ']':
        case '}':
        case ':':
            goto found;
        default:
            if ((unsigned char)c < 32u || (unsigned char)c >= 127u) {
                parser->pos = start;
                return JSMN_ERROR_INVAL;
            }
            break;
        }
    }

found:
    token = jsmn_alloc_token(parser, tokens, num_tokens);
    if (token == NULL) {
        parser->pos = start;
        return JSMN_ERROR_NOMEM;
    }
    jsmn_fill_token(token, JSMN_PRIMITIVE, (int)start, (int)parser->pos);
    token->parent = parser->toksuper;
    if (parser->pos > 0)
        parser->pos--;
    return 0;
}

static int jsmn_parse_string(
    jsmn_parser *parser,
    const char *js,
    size_t len,
    jsmntok_t *tokens,
    size_t num_tokens)
{
    const unsigned int start = parser->pos;
    jsmntok_t *token;

    parser->pos++;
    for (; parser->pos < len; parser->pos++) {
        const char c = js[parser->pos];
        if (c == '"') {
            token = jsmn_alloc_token(parser, tokens, num_tokens);
            if (token == NULL) {
                parser->pos = start;
                return JSMN_ERROR_NOMEM;
            }
            jsmn_fill_token(token, JSMN_STRING, (int)start + 1, (int)parser->pos);
            token->parent = parser->toksuper;
            return 0;
        }

        if (c == '\\') {
            parser->pos++;
            if (parser->pos >= len) {
                parser->pos = start;
                return JSMN_ERROR_PART;
            }
            switch (js[parser->pos]) {
            case '"':
            case '/':
            case '\\':
            case 'b':
            case 'f':
            case 'r':
            case 'n':
            case 't':
                break;
            case 'u': {
                int i;
                for (i = 0; i < 4; i++) {
                    parser->pos++;
                    if (parser->pos >= len || !isxdigit((unsigned char)js[parser->pos])) {
                        parser->pos = start;
                        return JSMN_ERROR_INVAL;
                    }
                }
                break;
            }
            default:
                parser->pos = start;
                return JSMN_ERROR_INVAL;
            }
        }
    }

    parser->pos = start;
    return JSMN_ERROR_PART;
}

static int jsmn_parse(
    jsmn_parser *parser,
    const char *js,
    size_t len,
    jsmntok_t *tokens,
    unsigned int num_tokens)
{
    int r;
    int i;
    jsmntok_t *token;

    for (; parser->pos < len; parser->pos++) {
        const char c = js[parser->pos];
        switch (c) {
        case '{':
        case '[':
            token = jsmn_alloc_token(parser, tokens, num_tokens);
            if (token == NULL)
                return JSMN_ERROR_NOMEM;
            if (parser->toksuper != -1) {
                tokens[parser->toksuper].size++;
                token->parent = parser->toksuper;
            }
            token->type = (c == '{' ? JSMN_OBJECT : JSMN_ARRAY);
            token->start = (int)parser->pos;
            parser->toksuper = (int)parser->toknext - 1;
            break;

        case '}':
        case ']': {
            const jsmntype_t type = (c == '}' ? JSMN_OBJECT : JSMN_ARRAY);
            for (i = (int)parser->toknext - 1; i >= 0; i--) {
                token = &tokens[i];
                if (token->start != -1 && token->end == -1) {
                    if (token->type != type)
                        return JSMN_ERROR_INVAL;
                    token->end = (int)parser->pos + 1;
                    parser->toksuper = token->parent;
                    break;
                }
            }
            if (i == -1)
                return JSMN_ERROR_INVAL;
            break;
        }

        case '"':
            r = jsmn_parse_string(parser, js, len, tokens, num_tokens);
            if (r < 0)
                return r;
            if (parser->toksuper != -1)
                tokens[parser->toksuper].size++;
            break;

        case '\t':
        case '\r':
        case '\n':
        case ' ':
            break;

        case ':':
            parser->toksuper = (int)parser->toknext - 1;
            break;

        case ',':
            if (parser->toksuper != -1 &&
                tokens[parser->toksuper].type != JSMN_ARRAY &&
                tokens[parser->toksuper].type != JSMN_OBJECT) {
                parser->toksuper = tokens[parser->toksuper].parent;
            }
            break;

        default:
            r = jsmn_parse_primitive(parser, js, len, tokens, num_tokens);
            if (r < 0)
                return r;
            if (parser->toksuper != -1)
                tokens[parser->toksuper].size++;
            break;
        }
    }

    for (i = (int)parser->toknext - 1; i >= 0; i--) {
        if (tokens[i].start != -1 && tokens[i].end == -1)
            return JSMN_ERROR_PART;
    }

    return (int)parser->toknext;
}

struct json_doc {
    const char *json;
    size_t len;
    jsmntok_t *tokens;
    int count;
};

static void set_error(char *error, size_t error_size, const char *message)
{
    if (error != NULL && error_size > 0)
        snprintf(error, error_size, "%s", message != NULL ? message : "unknown error");
}

static int json_open(struct json_doc *doc, const char *json, size_t len, char *error, size_t error_size)
{
    jsmn_parser parser;
    size_t capacity;
    int count;

    memset(doc, 0, sizeof(*doc));
    if (json == NULL || len == 0) {
        set_error(error, error_size, "empty JSON");
        return -1;
    }

    capacity = len / 2u + 512u;
    if (capacity < 1024u)
        capacity = 1024u;

    doc->tokens = calloc(capacity, sizeof(*doc->tokens));
    if (doc->tokens == NULL) {
        set_error(error, error_size, "JSON token allocation failed");
        return -1;
    }

    jsmn_init(&parser);
    count = jsmn_parse(&parser, json, len, doc->tokens, (unsigned int)capacity);
    if (count < 0) {
        free(doc->tokens);
        doc->tokens = NULL;
        if (count == JSMN_ERROR_NOMEM)
            set_error(error, error_size, "JSON token capacity exhausted");
        else if (count == JSMN_ERROR_PART)
            set_error(error, error_size, "JSON is incomplete");
        else
            set_error(error, error_size, "JSON parse error");
        return -1;
    }

    doc->json = json;
    doc->len = len;
    doc->count = count;
    if (count <= 0) {
        free(doc->tokens);
        doc->tokens = NULL;
        set_error(error, error_size, "JSON contains no tokens");
        return -1;
    }
    return 0;
}

static void json_close(struct json_doc *doc)
{
    free(doc->tokens);
    memset(doc, 0, sizeof(*doc));
}

static bool tok_eq(const struct json_doc *doc, int token_index, const char *text)
{
    const jsmntok_t *tok;
    size_t length;

    if (token_index < 0 || token_index >= doc->count || text == NULL)
        return false;
    tok = &doc->tokens[token_index];
    if (tok->type != JSMN_STRING)
        return false;
    length = (size_t)(tok->end - tok->start);
    return strlen(text) == length &&
           memcmp(doc->json + tok->start, text, length) == 0;
}

static int tok_next(const struct json_doc *doc, int token_index)
{
    const int end = doc->tokens[token_index].end;
    int i = token_index + 1;
    while (i < doc->count && doc->tokens[i].start < end)
        i++;
    return i;
}

static int obj_get(const struct json_doc *doc, int object_index, const char *key)
{
    int i;

    if (object_index < 0 || object_index >= doc->count ||
        doc->tokens[object_index].type != JSMN_OBJECT)
        return -1;

    i = object_index + 1;
    while (i < doc->count && doc->tokens[i].start < doc->tokens[object_index].end) {
        if (doc->tokens[i].type == JSMN_STRING &&
            doc->tokens[i].parent == object_index) {
            const int value_index = i + 1;
            if (value_index >= doc->count)
                return -1;
            if (tok_eq(doc, i, key))
                return value_index;
            i = tok_next(doc, value_index);
        } else {
            i++;
        }
    }
    return -1;
}

static int array_first(const struct json_doc *doc, int array_index)
{
    int i;
    if (array_index < 0 || array_index >= doc->count ||
        doc->tokens[array_index].type != JSMN_ARRAY)
        return -1;
    for (i = array_index + 1;
         i < doc->count && doc->tokens[i].start < doc->tokens[array_index].end;
         i++) {
        if (doc->tokens[i].parent == array_index)
            return i;
    }
    return -1;
}

static int array_next(const struct json_doc *doc, int array_index, int element_index)
{
    int i = tok_next(doc, element_index);
    while (i < doc->count && doc->tokens[i].start < doc->tokens[array_index].end) {
        if (doc->tokens[i].parent == array_index)
            return i;
        i++;
    }
    return -1;
}

static int hex_value(char c)
{
    if (c >= '0' && c <= '9')
        return c - '0';
    if (c >= 'a' && c <= 'f')
        return 10 + c - 'a';
    if (c >= 'A' && c <= 'F')
        return 10 + c - 'A';
    return -1;
}

static uint32_t parse_u16_escape(const char *p)
{
    uint32_t value = 0;
    int i;
    for (i = 0; i < 4; i++)
        value = (value << 4) | (uint32_t)hex_value(p[i]);
    return value;
}

static size_t utf8_encode(uint32_t cp, char *out, size_t remaining)
{
    if (cp <= 0x7Fu) {
        if (remaining < 1)
            return 0;
        out[0] = (char)cp;
        return 1;
    }
    if (cp <= 0x7FFu) {
        if (remaining < 2)
            return 0;
        out[0] = (char)(0xC0u | (cp >> 6));
        out[1] = (char)(0x80u | (cp & 0x3Fu));
        return 2;
    }
    if (cp <= 0xFFFFu) {
        if (remaining < 3)
            return 0;
        out[0] = (char)(0xE0u | (cp >> 12));
        out[1] = (char)(0x80u | ((cp >> 6) & 0x3Fu));
        out[2] = (char)(0x80u | (cp & 0x3Fu));
        return 3;
    }
    if (remaining < 4)
        return 0;
    out[0] = (char)(0xF0u | (cp >> 18));
    out[1] = (char)(0x80u | ((cp >> 12) & 0x3Fu));
    out[2] = (char)(0x80u | ((cp >> 6) & 0x3Fu));
    out[3] = (char)(0x80u | (cp & 0x3Fu));
    return 4;
}

static bool json_copy_string(
    const struct json_doc *doc,
    int token_index,
    char *out,
    size_t out_size)
{
    const jsmntok_t *tok;
    const char *p;
    const char *end;
    size_t written = 0;

    if (out == NULL || out_size == 0 || token_index < 0 || token_index >= doc->count)
        return false;
    out[0] = '\0';
    tok = &doc->tokens[token_index];
    if (tok->type != JSMN_STRING)
        return false;

    p = doc->json + tok->start;
    end = doc->json + tok->end;
    while (p < end && written + 1u < out_size) {
        unsigned char ch = (unsigned char)*p++;
        if (ch != '\\') {
            out[written++] = (char)ch;
            continue;
        }

        if (p >= end)
            return false;
        ch = (unsigned char)*p++;
        switch (ch) {
        case '"': out[written++] = '"'; break;
        case '\\': out[written++] = '\\'; break;
        case '/': out[written++] = '/'; break;
        case 'b': out[written++] = '\b'; break;
        case 'f': out[written++] = '\f'; break;
        case 'n': out[written++] = '\n'; break;
        case 'r': out[written++] = '\r'; break;
        case 't': out[written++] = '\t'; break;
        case 'u': {
            uint32_t cp;
            size_t bytes;
            if (end - p < 4)
                return false;
            cp = parse_u16_escape(p);
            p += 4;
            if (cp >= 0xD800u && cp <= 0xDBFFu &&
                end - p >= 6 && p[0] == '\\' && p[1] == 'u') {
                const uint32_t low = parse_u16_escape(p + 2);
                if (low >= 0xDC00u && low <= 0xDFFFu) {
                    cp = 0x10000u + ((cp - 0xD800u) << 10) + (low - 0xDC00u);
                    p += 6;
                }
            }
            bytes = utf8_encode(cp, out + written, out_size - written - 1u);
            if (bytes == 0)
                goto done;
            written += bytes;
            break;
        }
        default:
            return false;
        }
    }

done:
    out[written] = '\0';
    return true;
}

static int utf8_sequence_length(unsigned char c)
{
    if ((c & 0x80u) == 0)
        return 1;
    if ((c & 0xE0u) == 0xC0u)
        return 2;
    if ((c & 0xF0u) == 0xE0u)
        return 3;
    if ((c & 0xF8u) == 0xF0u)
        return 4;
    return 1;
}

static uint32_t utf8_decode_one(const unsigned char *p, int length)
{
    if (length == 1)
        return p[0];
    if (length == 2)
        return ((uint32_t)(p[0] & 0x1Fu) << 6) |
               (uint32_t)(p[1] & 0x3Fu);
    if (length == 3)
        return ((uint32_t)(p[0] & 0x0Fu) << 12) |
               ((uint32_t)(p[1] & 0x3Fu) << 6) |
               (uint32_t)(p[2] & 0x3Fu);
    return ((uint32_t)(p[0] & 0x07u) << 18) |
           ((uint32_t)(p[1] & 0x3Fu) << 12) |
           ((uint32_t)(p[2] & 0x3Fu) << 6) |
           (uint32_t)(p[3] & 0x3Fu);
}

static int json_string_utf16_length(const struct json_doc *doc, int token_index)
{
    const jsmntok_t *tok;
    const char *p;
    const char *end;
    int units = 0;

    if (token_index < 0 || token_index >= doc->count)
        return 0;
    tok = &doc->tokens[token_index];
    if (tok->type != JSMN_STRING)
        return 0;

    p = doc->json + tok->start;
    end = doc->json + tok->end;
    while (p < end) {
        const unsigned char ch = (unsigned char)*p;
        if (ch == '\\') {
            p++;
            if (p >= end)
                break;
            if (*p == 'u' && end - p >= 5) {
                units++;
                p += 5;
            } else {
                units++;
                p++;
            }
        } else if (ch < 0x80u) {
            units++;
            p++;
        } else {
            int n = utf8_sequence_length(ch);
            uint32_t cp;
            if (p + n > end)
                n = 1;
            cp = utf8_decode_one((const unsigned char *)p, n);
            units += cp > 0xFFFFu ? 2 : 1;
            p += n;
        }
    }
    return units;
}

static bool json_i64(const struct json_doc *doc, int token_index, int64_t *value)
{
    const jsmntok_t *tok;
    char buffer[64];
    size_t length;
    char *tail;
    long long parsed;

    if (token_index < 0 || token_index >= doc->count || value == NULL)
        return false;
    tok = &doc->tokens[token_index];
    if (tok->type != JSMN_PRIMITIVE)
        return false;
    length = (size_t)(tok->end - tok->start);
    if (length == 0 || length >= sizeof(buffer))
        return false;
    memcpy(buffer, doc->json + tok->start, length);
    buffer[length] = '\0';
    parsed = strtoll(buffer, &tail, 10);
    if (tail == buffer || *tail != '\0')
        return false;
    *value = (int64_t)parsed;
    return true;
}

static bool json_int(const struct json_doc *doc, int token_index, int *value)
{
    int64_t temp;
    if (!json_i64(doc, token_index, &temp) || temp < INT_MIN || temp > INT_MAX)
        return false;
    *value = (int)temp;
    return true;
}

static bool json_bool(const struct json_doc *doc, int token_index, bool *value)
{
    const jsmntok_t *tok;
    const size_t true_len = 4;
    const size_t false_len = 5;
    size_t length;

    if (token_index < 0 || token_index >= doc->count || value == NULL)
        return false;
    tok = &doc->tokens[token_index];
    if (tok->type != JSMN_PRIMITIVE)
        return false;
    length = (size_t)(tok->end - tok->start);
    if (length == true_len &&
        memcmp(doc->json + tok->start, "true", true_len) == 0) {
        *value = true;
        return true;
    }
    if (length == false_len &&
        memcmp(doc->json + tok->start, "false", false_len) == 0) {
        *value = false;
        return true;
    }
    return false;
}

static bool json_is_null(const struct json_doc *doc, int token_index)
{
    const jsmntok_t *tok;
    if (token_index < 0 || token_index >= doc->count)
        return false;
    tok = &doc->tokens[token_index];
    return tok->type == JSMN_PRIMITIVE &&
           tok->end - tok->start == 4 &&
           memcmp(doc->json + tok->start, "null", 4) == 0;
}

static int slide_ms_from_text_token(const struct json_doc *doc, int token_index)
{
    const int units = json_string_utf16_length(doc, token_index);
    const int value = 1500 + units * 55;
    return value > 2500 ? value : 2500;
}

static int parse_bump_array(
    const struct json_doc *doc,
    int array_index,
    struct sp_bump *out,
    int capacity,
    char *error,
    size_t error_size)
{
    int count = 0;
    int element = array_first(doc, array_index);

    while (element >= 0) {
        int id_token;
        int active_token;
        int range_token;
        int slides_token;
        struct sp_bump *bump;

        if (doc->tokens[element].type != JSMN_OBJECT) {
            set_error(error, error_size, "bump array contains non-object");
            return -1;
        }
        if (count >= capacity) {
            set_error(error, error_size, "too many bumps");
            return -1;
        }

        bump = &out[count];
        memset(bump, 0, sizeof(*bump));
        bump->active = true;

        id_token = obj_get(doc, element, "id");
        if (id_token < 0 ||
            !json_copy_string(doc, id_token, bump->id, sizeof(bump->id))) {
            set_error(error, error_size, "bump missing id");
            return -1;
        }

        active_token = obj_get(doc, element, "active");
        if (active_token >= 0) {
            bool active;
            if (json_bool(doc, active_token, &active))
                bump->active = active;
        }

        range_token = obj_get(doc, element, "date_range");
        if (range_token >= 0 && !json_is_null(doc, range_token)) {
            int first;
            int second;
            if (doc->tokens[range_token].type != JSMN_ARRAY) {
                set_error(error, error_size, "bump date_range is not array");
                return -1;
            }
            first = array_first(doc, range_token);
            second = first >= 0 ? array_next(doc, range_token, first) : -1;
            if (first < 0 || second < 0 ||
                !json_copy_string(doc, first, bump->date_start, sizeof(bump->date_start)) ||
                !json_copy_string(doc, second, bump->date_end, sizeof(bump->date_end))) {
                set_error(error, error_size, "bump date_range invalid");
                return -1;
            }
            bump->has_date_range = true;
        }

        slides_token = obj_get(doc, element, "slides");
        if (slides_token < 0 || doc->tokens[slides_token].type != JSMN_ARRAY) {
            set_error(error, error_size, "bump missing slides");
            return -1;
        }

        {
            int slide = array_first(doc, slides_token);
            while (slide >= 0) {
                int text_token;
                if (doc->tokens[slide].type != JSMN_OBJECT) {
                    set_error(error, error_size, "slide is not object");
                    return -1;
                }
                if (bump->slide_count >= SP_MAX_SLIDES) {
                    set_error(error, error_size, "too many slides in bump");
                    return -1;
                }
                text_token = obj_get(doc, slide, "text");
                if (text_token < 0 || doc->tokens[text_token].type != JSMN_STRING) {
                    set_error(error, error_size, "slide missing text");
                    return -1;
                }
                bump->slide_ms[bump->slide_count++] =
                    slide_ms_from_text_token(doc, text_token);
                slide = array_next(doc, slides_token, slide);
            }
        }

        count++;
        element = array_next(doc, array_index, element);
    }
    return count;
}

static int parse_items(
    const struct json_doc *doc,
    int array_index,
    struct sp_schedule *schedule,
    char *error,
    size_t error_size)
{
    int count = 0;
    int element = array_first(doc, array_index);

    while (element >= 0) {
        struct sp_item *item;
        int token;

        if (doc->tokens[element].type != JSMN_OBJECT) {
            set_error(error, error_size, "items array contains non-object");
            return -1;
        }
        if (count >= SP_MAX_ITEMS) {
            set_error(error, error_size, "too many program items");
            return -1;
        }

        item = &schedule->items[count];
        memset(item, 0, sizeof(*item));

        token = obj_get(doc, element, "id");
        if (token < 0 || !json_copy_string(doc, token, item->id, sizeof(item->id))) {
            set_error(error, error_size, "program item missing id");
            return -1;
        }

        token = obj_get(doc, element, "mp4");
        if (token < 0)
            token = obj_get(doc, element, "file");
        if (token < 0 || !json_copy_string(doc, token, item->mp4, sizeof(item->mp4))) {
            set_error(error, error_size, "program item missing mp4/file");
            return -1;
        }

        token = obj_get(doc, element, "title");
        if (token >= 0)
            (void)json_copy_string(doc, token, item->title, sizeof(item->title));
        if (item->title[0] == '\0')
            snprintf(item->title, sizeof(item->title), "%s", item->id);

        token = obj_get(doc, element, "year");
        if (token >= 0) {
            if (doc->tokens[token].type == JSMN_STRING) {
                (void)json_copy_string(doc, token, item->year, sizeof(item->year));
            } else {
                int year;
                if (json_int(doc, token, &year))
                    snprintf(item->year, sizeof(item->year), "%d", year);
            }
        }

        token = obj_get(doc, element, "duration");
        if (token < 0 || !json_int(doc, token, &item->duration_s) || item->duration_s <= 0) {
            set_error(error, error_size, "program item has invalid duration");
            return -1;
        }

        token = obj_get(doc, element, "inS");
        if (token >= 0)
            (void)json_int(doc, token, &item->in_s);

        token = obj_get(doc, element, "offAir");
        if (token >= 0)
            (void)json_bool(doc, token, &item->off_air);

        count++;
        element = array_next(doc, array_index, element);
    }

    schedule->item_count = count;
    return count;
}

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
    size_t error_size)
{
    struct json_doc doc;
    int channels;
    int channel;
    bool found = false;

    if (pointer == NULL) {
        set_error(error, error_size, "pointer output is null");
        return -1;
    }
    memset(pointer, 0, sizeof(*pointer));
    if (channel_name != NULL && channel_name_size)
        channel_name[0] = '\0';
    if (channel_id != NULL && channel_id_size)
        channel_id[0] = '\0';

    if (json_open(&doc, json, json_len, error, error_size) != 0)
        return -1;
    if (doc.tokens[0].type != JSMN_OBJECT) {
        json_close(&doc);
        set_error(error, error_size, "lineup root is not object");
        return -1;
    }

    channels = obj_get(&doc, 0, "channels");
    if (channels < 0 || doc.tokens[channels].type != JSMN_ARRAY) {
        json_close(&doc);
        set_error(error, error_size, "lineup missing channels");
        return -1;
    }

    channel = array_first(&doc, channels);
    while (channel >= 0) {
        int dial_token = obj_get(&doc, channel, "dial");
        int dial = -1;
        if (dial_token >= 0 && json_int(&doc, dial_token, &dial) && dial == 53) {
            int token;
            int versions;
            int version_token;
            bool have_selected = false;
            int64_t best_effective = INT64_MIN;
            struct sp_pointer earliest;
            bool have_earliest = false;
            int64_t earliest_effective = INT64_MAX;

            memset(&earliest, 0, sizeof(earliest));
            token = obj_get(&doc, channel, "name");
            if (token >= 0 && channel_name != NULL)
                (void)json_copy_string(&doc, token, channel_name, channel_name_size);
            token = obj_get(&doc, channel, "id");
            if (token >= 0 && channel_id != NULL)
                (void)json_copy_string(&doc, token, channel_id, channel_id_size);

            versions = obj_get(&doc, channel, "versions");
            if (versions < 0 || doc.tokens[versions].type != JSMN_ARRAY) {
                json_close(&doc);
                set_error(error, error_size, "TOONERTIA missing versions");
                return -1;
            }

            version_token = array_first(&doc, versions);
            while (version_token >= 0) {
                struct sp_pointer candidate;
                int value_token;
                int64_t temp64;
                memset(&candidate, 0, sizeof(candidate));

                value_token = obj_get(&doc, version_token, "v");
                if (value_token < 0 || !json_int(&doc, value_token, &candidate.version)) {
                    json_close(&doc);
                    set_error(error, error_size, "version pointer missing v");
                    return -1;
                }
                value_token = obj_get(&doc, version_token, "manifest");
                if (value_token < 0 ||
                    !json_copy_string(&doc, value_token, candidate.manifest, sizeof(candidate.manifest))) {
                    json_close(&doc);
                    set_error(error, error_size, "version pointer missing manifest");
                    return -1;
                }
                value_token = obj_get(&doc, version_token, "epochMs");
                if (value_token < 0 || !json_i64(&doc, value_token, &candidate.epoch_ms)) {
                    json_close(&doc);
                    set_error(error, error_size, "version pointer missing epochMs");
                    return -1;
                }
                candidate.effective_ms = candidate.epoch_ms;
                value_token = obj_get(&doc, version_token, "effectiveAtMs");
                if (value_token >= 0 && json_i64(&doc, value_token, &temp64))
                    candidate.effective_ms = temp64;
                value_token = obj_get(&doc, version_token, "startIndex");
                if (value_token >= 0)
                    (void)json_int(&doc, value_token, &candidate.start_index);

                if (!have_earliest || candidate.effective_ms < earliest_effective ||
                    (candidate.effective_ms == earliest_effective &&
                     candidate.version > earliest.version)) {
                    earliest = candidate;
                    earliest_effective = candidate.effective_ms;
                    have_earliest = true;
                }
                if (candidate.effective_ms <= now_ms &&
                    (!have_selected || candidate.effective_ms > best_effective ||
                     (candidate.effective_ms == best_effective &&
                      candidate.version > pointer->version))) {
                    *pointer = candidate;
                    best_effective = candidate.effective_ms;
                    have_selected = true;
                }

                version_token = array_next(&doc, versions, version_token);
            }

            if (!have_selected && have_earliest)
                *pointer = earliest;
            if (!have_selected && !have_earliest) {
                json_close(&doc);
                set_error(error, error_size, "TOONERTIA has no versions");
                return -1;
            }
            found = true;
            break;
        }
        channel = array_next(&doc, channels, channel);
    }

    json_close(&doc);
    if (!found) {
        set_error(error, error_size, "channel 53 / TOONERTIA not found");
        return -1;
    }
    return 0;
}

int sp_parse_manifest(
    const char *json,
    size_t json_len,
    struct sp_schedule *schedule,
    char *error,
    size_t error_size)
{
    struct json_doc doc;
    int token;

    if (schedule == NULL) {
        set_error(error, error_size, "schedule output is null");
        return -1;
    }
    memset(schedule, 0, sizeof(*schedule));

    if (json_open(&doc, json, json_len, error, error_size) != 0)
        return -1;
    if (doc.tokens[0].type != JSMN_OBJECT) {
        json_close(&doc);
        set_error(error, error_size, "manifest root is not object");
        return -1;
    }

    token = obj_get(&doc, 0, "engine");
    if (token < 0 || !json_int(&doc, token, &schedule->engine)) {
        json_close(&doc);
        set_error(error, error_size, "manifest missing engine");
        return -1;
    }

    token = obj_get(&doc, 0, "version");
    if (token < 0 || !json_int(&doc, token, &schedule->version)) {
        json_close(&doc);
        set_error(error, error_size, "manifest missing version");
        return -1;
    }

    token = obj_get(&doc, 0, "channel");
    if (token < 0 ||
        !json_copy_string(&doc, token, schedule->channel, sizeof(schedule->channel))) {
        json_close(&doc);
        set_error(error, error_size, "manifest missing channel");
        return -1;
    }

    token = obj_get(&doc, 0, "platform");
    if (token >= 0 && !json_is_null(&doc, token))
        (void)json_copy_string(&doc, token, schedule->platform_path, sizeof(schedule->platform_path));

    schedule->has_block = obj_get(&doc, 0, "block") >= 0;
    schedule->has_ads = obj_get(&doc, 0, "ads") >= 0;

    token = obj_get(&doc, 0, "items");
    if (token < 0 || doc.tokens[token].type != JSMN_ARRAY ||
        parse_items(&doc, token, schedule, error, error_size) <= 0) {
        json_close(&doc);
        if (error != NULL && error[0] == '\0')
            set_error(error, error_size, "manifest missing items");
        return -1;
    }

    token = obj_get(&doc, 0, "bumps");
    if (token >= 0 && doc.tokens[token].type == JSMN_ARRAY) {
        const int count = parse_bump_array(
            &doc, token, schedule->channel_bumps, SP_MAX_BUMPS, error, error_size);
        if (count < 0) {
            json_close(&doc);
            return -1;
        }
        schedule->channel_bump_count = count;
    }

    json_close(&doc);

    if (schedule->engine != 5) {
        set_error(error, error_size, "TOONERTIA engine is not version 5");
        return -1;
    }
    if (strcmp(schedule->channel, "toonertia") != 0) {
        set_error(error, error_size, "manifest channel is not toonertia");
        return -1;
    }
    if (schedule->has_block || schedule->has_ads) {
        set_error(error, error_size, "TOONERTIA now uses block/ads; V6C safety stop");
        return -1;
    }
    if (schedule->platform_path[0] == '\0') {
        set_error(error, error_size, "manifest missing platform file");
        return -1;
    }
    return 0;
}

int sp_parse_platform(
    const char *json,
    size_t json_len,
    struct sp_schedule *schedule,
    char *error,
    size_t error_size)
{
    struct json_doc doc;
    int token;
    int engine = 0;

    if (schedule == NULL) {
        set_error(error, error_size, "schedule is null");
        return -1;
    }
    if (json_open(&doc, json, json_len, error, error_size) != 0)
        return -1;
    if (doc.tokens[0].type != JSMN_OBJECT) {
        json_close(&doc);
        set_error(error, error_size, "platform root is not object");
        return -1;
    }

    token = obj_get(&doc, 0, "engine");
    if (token >= 0)
        (void)json_int(&doc, token, &engine);
    if (engine != 5) {
        json_close(&doc);
        set_error(error, error_size, "platform engine is not version 5");
        return -1;
    }

    token = obj_get(&doc, 0, "bumps");
    if (token < 0 || doc.tokens[token].type != JSMN_ARRAY) {
        json_close(&doc);
        set_error(error, error_size, "platform missing bumps");
        return -1;
    }

    {
        const int count = parse_bump_array(
            &doc, token, schedule->platform_bumps, SP_MAX_BUMPS, error, error_size);
        if (count <= 0) {
            json_close(&doc);
            if (error != NULL && error[0] == '\0')
                set_error(error, error_size, "platform has no bumps");
            return -1;
        }
        schedule->platform_bump_count = count;
    }

    json_close(&doc);
    return 0;
}

static uint32_t js_hash_ascii(const char *text)
{
    uint32_t hash = 0;
    const unsigned char *p = (const unsigned char *)text;
    while (*p != '\0')
        hash = hash * 31u + (uint32_t)*p++;
    return hash;
}

struct sp_rng {
    uint32_t state;
};

static uint32_t rng_next(struct sp_rng *rng)
{
    uint32_t t;
    uint32_t n;
    rng->state += 1831565813u;
    t = rng->state;
    n = (t ^ (t >> 15)) * (1u | t);
    n ^= n + ((n ^ (n >> 7)) * (61u | n));
    return n ^ (n >> 14);
}

static int rng_index(struct sp_rng *rng, int count)
{
    const uint32_t value = rng_next(rng);
    return count <= 1 ? 0 : (int)(((uint64_t)value * (uint64_t)(unsigned)count) >> 32);
}

static bool parse_two_digits(const char *text, int *value)
{
    if (text == NULL || !isdigit((unsigned char)text[0]) || !isdigit((unsigned char)text[1]))
        return false;
    *value = (text[0] - '0') * 10 + (text[1] - '0');
    return true;
}

static bool parse_ymd(const char *text, int *year, int *month, int *day)
{
    char year_buf[5];
    if (text == NULL || strlen(text) < 10 ||
        text[4] != '-' || text[7] != '-')
        return false;
    memcpy(year_buf, text, 4);
    year_buf[4] = '\0';
    *year = atoi(year_buf);
    return parse_two_digits(text + 5, month) && parse_two_digits(text + 8, day);
}

static bool utc_parts(int64_t at_ms, int *year, int *month, int *day)
{
    time_t seconds = (time_t)(at_ms / 1000);
    struct tm value;
#if defined(_WIN32)
    if (gmtime_s(&value, &seconds) != 0)
        return false;
#else
    if (gmtime_r(&seconds, &value) == NULL)
        return false;
#endif
    *year = value.tm_year + 1900;
    *month = value.tm_mon + 1;
    *day = value.tm_mday;
    return true;
}

static bool date_range_active(const struct sp_bump *bump, int64_t at_ms)
{
    int year;
    int month;
    int day;

    if (!bump->has_date_range)
        return false;
    if (!utc_parts(at_ms, &year, &month, &day))
        return false;

    if (strlen(bump->date_start) >= 5 &&
        isdigit((unsigned char)bump->date_start[0]) &&
        isdigit((unsigned char)bump->date_start[1]) &&
        isdigit((unsigned char)bump->date_start[2]) &&
        isdigit((unsigned char)bump->date_start[3]) &&
        bump->date_start[4] == '-') {
        int sy, sm, sd, ey, em, ed;
        int current;
        int start;
        int end;
        if (!parse_ymd(bump->date_start, &sy, &sm, &sd) ||
            !parse_ymd(bump->date_end, &ey, &em, &ed))
            return false;
        current = year * 10000 + month * 100 + day;
        start = sy * 10000 + sm * 100 + sd;
        end = ey * 10000 + em * 100 + ed;
        return current >= start && current <= end;
    } else {
        int sm, sd, em, ed;
        int current = month * 100 + day;
        int start;
        int end;
        if (strlen(bump->date_start) < 5 || strlen(bump->date_end) < 5 ||
            bump->date_start[2] != '-' || bump->date_end[2] != '-' ||
            !parse_two_digits(bump->date_start, &sm) ||
            !parse_two_digits(bump->date_start + 3, &sd) ||
            !parse_two_digits(bump->date_end, &em) ||
            !parse_two_digits(bump->date_end + 3, &ed))
            return false;
        start = sm * 100 + sd;
        end = em * 100 + ed;
        return start <= end ? (current >= start && current <= end)
                            : (current >= start || current <= end);
    }
}

static int filter_bumps(
    const struct sp_bump *bumps,
    int bump_count,
    int64_t at_ms,
    int *indices,
    int capacity,
    char *season_key,
    size_t season_key_size)
{
    bool any_active_seasonal = false;
    int i;
    int count = 0;
    size_t key_used = 0;

    if (season_key != NULL && season_key_size > 0)
        season_key[0] = '\0';

    for (i = 0; i < bump_count; i++) {
        if (!bumps[i].active || !bumps[i].has_date_range)
            continue;
        if (date_range_active(&bumps[i], at_ms)) {
            any_active_seasonal = true;
            if (season_key != NULL && season_key_size > 0) {
                const char *id = bumps[i].id;
                const size_t id_len = strlen(id);
                if (key_used != 0 && key_used + 1 < season_key_size)
                    season_key[key_used++] = '|';
                if (key_used + id_len < season_key_size) {
                    memcpy(season_key + key_used, id, id_len);
                    key_used += id_len;
                    season_key[key_used] = '\0';
                }
            }
        }
    }

    for (i = 0; i < bump_count; i++) {
        bool include;
        if (!bumps[i].active)
            continue;
        if (any_active_seasonal)
            include = !bumps[i].has_date_range || date_range_active(&bumps[i], at_ms);
        else
            include = !bumps[i].has_date_range;
        if (include) {
            if (count >= capacity)
                return -1;
            indices[count++] = i;
        }
    }
    return count;
}

static int index_in_array(const int *values, int count, int needle)
{
    int i;
    for (i = 0; i < count; i++) {
        if (values[i] == needle)
            return i;
    }
    return -1;
}

static int deck_shuffle(
    const int *filtered,
    int filtered_count,
    const struct sp_deck_state *deck,
    uint32_t seed,
    int *order)
{
    struct sp_rng rng;
    int thresholds[SP_MAX_BUMPS];
    int half;
    int recent_limit;
    int i;

    if (filtered_count <= 0 || filtered_count > SP_MAX_BUMPS)
        return -1;

    rng.state = seed;
    memcpy(order, filtered, (size_t)filtered_count * sizeof(order[0]));

    for (i = filtered_count - 1; i > 0; i--) {
        const int j = rng_index(&rng, i + 1);
        const int temp = order[i];
        order[i] = order[j];
        order[j] = temp;
    }

    memset(thresholds, 0, sizeof(thresholds));
    half = filtered_count / 2;
    recent_limit = half < deck->recent_count ? half : deck->recent_count;

    for (i = recent_limit; i >= 1; i--) {
        const int bump_index = deck->recent[deck->recent_count - i];
        if (bump_index >= 0 && bump_index < SP_MAX_BUMPS)
            thresholds[bump_index] = half + 1 - i;
    }

    for (i = 1; i <= recent_limit; i++) {
        const int bump_index = deck->recent[deck->recent_count - i];
        const int d = index_in_array(order, filtered_count, bump_index);
        int candidates[SP_MAX_BUMPS];
        int candidate_count = 0;
        int p;
        int chosen;
        int temp;

        if (bump_index < 0 || bump_index >= SP_MAX_BUMPS)
            continue;
        if (d < 0 || d >= thresholds[bump_index])
            continue;

        for (p = thresholds[bump_index]; p < filtered_count; p++) {
            const int other = order[p];
            const int threshold = (other >= 0 && other < SP_MAX_BUMPS) ? thresholds[other] : 0;
            if (threshold <= d)
                candidates[candidate_count++] = p;
        }
        if (candidate_count <= 0)
            continue;

        chosen = candidates[rng_index(&rng, candidate_count)];
        temp = order[d];
        order[d] = order[chosen];
        order[chosen] = temp;
    }

    return filtered_count;
}

static int select_channel_bump(
    const struct sp_schedule *schedule,
    struct sp_deck_state *deck,
    int64_t at_ms,
    const char *cycle_seed)
{
    int filtered[SP_MAX_BUMPS];
    char season_key[SP_KEY_BYTES];
    int filtered_count;

    filtered_count = filter_bumps(
        schedule->channel_bumps,
        schedule->channel_bump_count,
        at_ms,
        filtered,
        SP_MAX_BUMPS,
        season_key,
        sizeof(season_key));
    if (filtered_count <= 0)
        return -1;

    if (strcmp(deck->key, season_key) != 0 || deck->pos >= deck->order_count) {
        char seed_text[256];
        const int seed_round = deck->rounds++;
        snprintf(seed_text, sizeof(seed_text), "toonertia-deck-%s-%d", cycle_seed, seed_round);
        if (deck_shuffle(
                filtered,
                filtered_count,
                deck,
                js_hash_ascii(seed_text),
                deck->order) <= 0)
            return -1;
        deck->order_count = filtered_count;
        deck->pos = 0;
        snprintf(deck->key, sizeof(deck->key), "%s", season_key);
    }

    {
        const int selected = deck->order[deck->pos++];
        if (deck->recent_count < (int)(sizeof(deck->recent) / sizeof(deck->recent[0]))) {
            deck->recent[deck->recent_count++] = selected;
        } else {
            memmove(deck->recent, deck->recent + 1,
                    (sizeof(deck->recent) / sizeof(deck->recent[0]) - 1u) * sizeof(deck->recent[0]));
            deck->recent[(sizeof(deck->recent) / sizeof(deck->recent[0])) - 1u] = selected;
        }

        if (deck->recent_count > deck->order_count) {
            memmove(deck->recent, deck->recent + 1,
                    (size_t)(deck->recent_count - 1) * sizeof(deck->recent[0]));
            deck->recent_count--;
        }
        return selected;
    }
}

static int select_platform_bump(
    const struct sp_schedule *schedule,
    int break_index,
    int64_t at_ms,
    const char *cycle_seed)
{
    int filtered[SP_MAX_BUMPS];
    char unused_key[2];
    char seed_text[256];
    struct sp_rng rng;
    int count;

    count = filter_bumps(
        schedule->platform_bumps,
        schedule->platform_bump_count,
        at_ms,
        filtered,
        SP_MAX_BUMPS,
        unused_key,
        sizeof(unused_key));
    if (count <= 0)
        return -1;

    snprintf(seed_text, sizeof(seed_text), "spelunkr-break-%d-%s", break_index, cycle_seed);
    rng.state = js_hash_ascii(seed_text);
    return filtered[rng_index(&rng, count)];
}

static int bump_slide_sum(const struct sp_bump *bump)
{
    int total = 0;
    int i;
    for (i = 0; i < bump->slide_count; i++)
        total += bump->slide_ms[i];
    return total;
}

static int64_t bump_break_duration_ms(
    const struct sp_bump *channel_bump,
    const struct sp_bump *platform_bump)
{
    return 3500ll +
           bump_slide_sum(channel_bump) +
           1000ll +
           1000ll +
           300ll +
           bump_slide_sum(platform_bump) +
           1000ll +
           1000ll;
}

static int build_cycle(
    const struct sp_schedule *schedule,
    const struct sp_pointer *pointer,
    int cycle_index,
    int64_t cycle_start_ms,
    struct sp_deck_state *deck,
    struct sp_cycle *cycle,
    char *error,
    size_t error_size)
{
    int first_item;
    int item_index;
    char cycle_seed[64];
    int64_t offset = 0;

    memset(cycle, 0, sizeof(*cycle));
    cycle->cycle_index = cycle_index;
    cycle->start_ms = cycle_start_ms;
    deck->rounds = 0;

    first_item = cycle_index == 0 ? pointer->start_index : 0;
    if (first_item < 0 || first_item >= schedule->item_count) {
        set_error(error, error_size, "startIndex outside manifest items");
        return -1;
    }
    snprintf(cycle_seed, sizeof(cycle_seed), "%d.%d", schedule->version, cycle_index);

    for (item_index = first_item; item_index < schedule->item_count; item_index++) {
        const struct sp_item *item = &schedule->items[item_index];
        int channel_bump;
        int platform_bump;
        int break_index;
        int64_t absolute_break_ms;
        int64_t duration;

        if (cycle->entry_count >= SP_MAX_ENTRIES) {
            set_error(error, error_size, "cycle entry capacity exceeded");
            return -1;
        }
        cycle->entries[cycle->entry_count++] = (struct sp_cycle_entry){
            .kind = SP_SEGMENT_SHOW,
            .off_ms = offset,
            .duration_ms = (int64_t)item->duration_s * 1000ll,
            .item_index = item_index,
            .channel_bump_index = -1,
            .platform_bump_index = -1,
        };
        offset += (int64_t)item->duration_s * 1000ll;

        absolute_break_ms = cycle_start_ms + offset;
        break_index = item_index;
        channel_bump = select_channel_bump(schedule, deck, absolute_break_ms, cycle_seed);
        platform_bump = select_platform_bump(
            schedule, break_index, absolute_break_ms, cycle_seed);
        if (channel_bump < 0 || platform_bump < 0) {
            set_error(error, error_size, "could not select channel/platform bump");
            return -1;
        }

        duration = bump_break_duration_ms(
            &schedule->channel_bumps[channel_bump],
            &schedule->platform_bumps[platform_bump]);

        if (cycle->entry_count >= SP_MAX_ENTRIES) {
            set_error(error, error_size, "cycle entry capacity exceeded");
            return -1;
        }
        cycle->entries[cycle->entry_count++] = (struct sp_cycle_entry){
            .kind = SP_SEGMENT_BUMP,
            .off_ms = offset,
            .duration_ms = duration,
            .item_index = -1,
            .channel_bump_index = channel_bump,
            .platform_bump_index = platform_bump,
        };
        offset += duration;
    }

    cycle->length_ms = offset;
    return 0;
}

static bool uri_unreserved(unsigned char c)
{
    return (c >= 'A' && c <= 'Z') ||
           (c >= 'a' && c <= 'z') ||
           (c >= '0' && c <= '9') ||
           c == '-' || c == '_' || c == '.' ||
           c == '!' || c == '~' || c == '*' || c == '\'' || c == '(' || c == ')';
}

static bool append_text(char *out, size_t out_size, size_t *used, const char *text)
{
    const size_t length = strlen(text);
    if (*used + length + 1u > out_size)
        return false;
    memcpy(out + *used, text, length);
    *used += length;
    out[*used] = '\0';
    return true;
}

static bool append_uri_component(char *out, size_t out_size, size_t *used, const char *text)
{
    static const char hex[] = "0123456789ABCDEF";
    const unsigned char *p = (const unsigned char *)text;
    while (*p != '\0') {
        const unsigned char c = *p++;
        if (uri_unreserved(c)) {
            if (*used + 2u > out_size)
                return false;
            out[(*used)++] = (char)c;
        } else {
            if (*used + 4u > out_size)
                return false;
            out[(*used)++] = '%';
            out[(*used)++] = hex[c >> 4];
            out[(*used)++] = hex[c & 0x0Fu];
        }
    }
    out[*used] = '\0';
    return true;
}

static bool make_archive_url(
    const struct sp_item *item,
    char *out,
    size_t out_size)
{
    size_t used = 0;
    if (out_size == 0)
        return false;
    out[0] = '\0';
    return append_text(out, out_size, &used, "https://archive.org/download/") &&
           append_uri_component(out, out_size, &used, item->id) &&
           append_text(out, out_size, &used, "/") &&
           append_uri_component(out, out_size, &used, item->mp4);
}

int sp_find_now(
    const struct sp_schedule *schedule,
    const struct sp_pointer *pointer,
    int64_t now_ms,
    struct sp_now *out,
    char *error,
    size_t error_size)
{
    struct sp_deck_state deck;
    struct sp_cycle cycle;
    int cycle_index = 0;
    int64_t cycle_start;
    int i;

    if (schedule == NULL || pointer == NULL || out == NULL) {
        set_error(error, error_size, "sp_find_now got null argument");
        return -1;
    }
    memset(out, 0, sizeof(*out));
    memset(&deck, 0, sizeof(deck));

    if (schedule->version != pointer->version) {
        set_error(error, error_size, "manifest version does not match lineup pointer");
        return -1;
    }
    if (schedule->item_count <= 0 ||
        schedule->channel_bump_count <= 0 ||
        schedule->platform_bump_count <= 0) {
        set_error(error, error_size, "schedule data incomplete");
        return -1;
    }
    if (now_ms < pointer->epoch_ms) {
        set_error(error, error_size, "Xbox clock is before TOONERTIA epoch");
        return -1;
    }

    cycle_start = pointer->epoch_ms;
    for (cycle_index = 0; cycle_index < 128; cycle_index++) {
        if (build_cycle(
                schedule,
                pointer,
                cycle_index,
                cycle_start,
                &deck,
                &cycle,
                error,
                error_size) != 0)
            return -1;

        if (now_ms < cycle_start + cycle.length_ms)
            break;
        cycle_start += cycle.length_ms;
    }
    if (cycle_index >= 128) {
        set_error(error, error_size, "too many cycles from epoch");
        return -1;
    }

    {
        const int64_t elapsed = now_ms - cycle.start_ms;
        const struct sp_cycle_entry *entry = NULL;
        int entry_index = -1;

        for (i = 0; i < cycle.entry_count; i++) {
            const int64_t start = cycle.entries[i].off_ms;
            const int64_t end = start + cycle.entries[i].duration_ms;
            if (elapsed >= start && elapsed < end) {
                entry = &cycle.entries[i];
                entry_index = i;
                break;
            }
        }

        if (entry == NULL) {
            set_error(error, error_size, "now is outside computed cycle entries");
            return -1;
        }

        out->ok = true;
        out->kind = entry->kind;
        out->version = schedule->version;
        out->cycle = cycle.cycle_index;
        out->entry_index = entry_index;
        out->item_index = entry->item_index;
        out->now_ms = now_ms;
        out->segment_start_ms = cycle.start_ms + entry->off_ms;
        out->segment_length_ms = entry->duration_ms;
        out->offset_ms = now_ms - out->segment_start_ms;
        out->remaining_ms = entry->duration_ms - out->offset_ms;

        if (entry->kind == SP_SEGMENT_SHOW) {
            const struct sp_item *item = &schedule->items[entry->item_index];
            snprintf(out->title, sizeof(out->title), "%s", item->title);
            snprintf(out->year, sizeof(out->year), "%s", item->year);
            snprintf(out->id, sizeof(out->id), "%s", item->id);
            snprintf(out->mp4, sizeof(out->mp4), "%s", item->mp4);
            if (!make_archive_url(item, out->archive_url, sizeof(out->archive_url))) {
                set_error(error, error_size, "Archive.org URL exceeded buffer");
                return -1;
            }
        } else if (entry->kind == SP_SEGMENT_BUMP) {
            if (entry->channel_bump_index >= 0 &&
                entry->channel_bump_index < schedule->channel_bump_count)
                snprintf(
                    out->channel_bump_id,
                    sizeof(out->channel_bump_id),
                    "%s",
                    schedule->channel_bumps[entry->channel_bump_index].id);
            if (entry->platform_bump_index >= 0 &&
                entry->platform_bump_index < schedule->platform_bump_count)
                snprintf(
                    out->platform_bump_id,
                    sizeof(out->platform_bump_id),
                    "%s",
                    schedule->platform_bumps[entry->platform_bump_index].id);
        }
    }

    return 0;
}

const char *sp_segment_kind_name(enum sp_segment_kind kind)
{
    switch (kind) {
    case SP_SEGMENT_SHOW:
        return "SHOW";
    case SP_SEGMENT_BUMP:
        return "BUMP";
    default:
        return "NONE";
    }
}
