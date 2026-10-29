#include <curl/curl.h>
#include <stdarg.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

struct range_probe {
    curl_off_t total;
};

/* GNU ld --wrap supplies this alias for the real libcurl symbol. */
CURLcode __real_curl_easy_getinfo(CURL *curl, CURLINFO info, ...);

static unsigned char lower_ascii(unsigned char c)
{
    return (c >= 'A' && c <= 'Z') ? (unsigned char)(c + ('a' - 'A')) : c;
}

static bool header_name_is(const char *data, size_t length, const char *name)
{
    size_t i;
    const size_t name_len = strlen(name);
    if (length < name_len + 1u || data[name_len] != ':')
        return false;
    for (i = 0; i < name_len; i++) {
        if (lower_ascii((unsigned char)data[i]) != lower_ascii((unsigned char)name[i]))
            return false;
    }
    return true;
}

static size_t probe_header(char *data, size_t size, size_t count, void *user)
{
    struct range_probe *probe = user;
    const size_t length = size * count;
    const char *slash;
    char number[32];
    size_t n = 0;
    unsigned long long value;

    if (probe == NULL || data == NULL || !header_name_is(data, length, "Content-Range"))
        return length;

    slash = memchr(data, '/', length);
    if (slash == NULL)
        return length;
    slash++;
    while ((size_t)(slash - data) < length && (*slash == ' ' || *slash == '\t'))
        slash++;
    if ((size_t)(slash - data) >= length || *slash == '*')
        return length;

    while ((size_t)(slash - data) < length && *slash >= '0' && *slash <= '9' && n + 1u < sizeof(number))
        number[n++] = *slash++;
    if (n == 0)
        return length;
    number[n] = '\0';
    value = strtoull(number, NULL, 10);
    if (value > 0)
        probe->total = (curl_off_t)value;
    return length;
}

static size_t probe_body(char *data, size_t size, size_t count, void *user)
{
    const size_t length = size * count;
    (void)data;
    (void)user;
    /* bytes=0-0 should only contain one byte. If a server ignores Range,
     * abort rather than stream a multi-gigabyte video just to discover size. */
    return length <= 8u ? length : 0u;
}

static curl_off_t probe_total_size(const char *url)
{
    struct range_probe probe = { 0 };
    CURL *curl;
    CURLcode rc;
    long http = 0;

    if (url == NULL || url[0] == '\0')
        return -1;

    curl = curl_easy_init();
    if (curl == NULL)
        return -1;

    curl_easy_setopt(curl, CURLOPT_URL, url);
    curl_easy_setopt(curl, CURLOPT_CAINFO, "cacert.pem");
    curl_easy_setopt(curl, CURLOPT_FOLLOWLOCATION, 1L);
    curl_easy_setopt(curl, CURLOPT_CONNECTTIMEOUT_MS, 15000L);
    curl_easy_setopt(curl, CURLOPT_TIMEOUT_MS, 30000L);
    curl_easy_setopt(curl, CURLOPT_LOW_SPEED_LIMIT, 1L);
    curl_easy_setopt(curl, CURLOPT_LOW_SPEED_TIME, 15L);
    curl_easy_setopt(curl, CURLOPT_USERAGENT, "Spelunkr360/0.7.0-rangefix2 (Xbox 360 homebrew)");
    curl_easy_setopt(curl, CURLOPT_RANGE, "0-0");
    curl_easy_setopt(curl, CURLOPT_HEADERFUNCTION, probe_header);
    curl_easy_setopt(curl, CURLOPT_HEADERDATA, &probe);
    curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, probe_body);
    curl_easy_setopt(curl, CURLOPT_WRITEDATA, &probe);

    rc = curl_easy_perform(curl);
    (void)__real_curl_easy_getinfo(curl, CURLINFO_RESPONSE_CODE, &http);
    curl_easy_cleanup(curl);

    if (probe.total > 0 && http == 206)
        return probe.total;
    if (probe.total > 0 && rc == CURLE_WRITE_ERROR)
        return probe.total;
    return -1;
}

/* curl-xenon may not implement the newer CURLINFO_CONTENT_LENGTH_DOWNLOAD_T
 * query even though the header exposes it. The previous wrapper only probed
 * when that query returned CURLE_OK, which meant an unsupported getinfo path
 * skipped the range fallback completely. Always repair this one query when
 * the returned length is unavailable OR the underlying getinfo call fails. */
CURLcode __wrap_curl_easy_getinfo(CURL *curl, CURLINFO info, ...)
{
    va_list args;
    void *out;
    CURLcode rc;

    va_start(args, info);
    out = va_arg(args, void *);
    va_end(args);
    if (out == NULL)
        return CURLE_BAD_FUNCTION_ARGUMENT;

    rc = __real_curl_easy_getinfo(curl, info, out);
    if (info == CURLINFO_CONTENT_LENGTH_DOWNLOAD_T) {
        curl_off_t *length = out;
        if (rc != CURLE_OK || *length <= 0) {
            char *effective_url = NULL;
            if (__real_curl_easy_getinfo(curl, CURLINFO_EFFECTIVE_URL, &effective_url) == CURLE_OK &&
                effective_url != NULL && effective_url[0] != '\0') {
                const curl_off_t probed = probe_total_size(effective_url);
                if (probed > 0) {
                    *length = probed;
                    return CURLE_OK;
                }
            }
        }
    }
    return rc;
}
