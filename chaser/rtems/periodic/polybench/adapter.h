#ifndef CHASER_POLYBENCH_ADAPTER_H
#define CHASER_POLYBENCH_ADAPTER_H
#include <stdint.h>
#include <stdio.h>
#include <stdarg.h>
#include <stdlib.h>
/* Scalar variables remain outside the array analysis region. */
#define PB_STORAGE(name) __attribute__((section(".chaser_data." #name), aligned(64)))
static uint32_t pb_hash;
static int pb_emit = 1;
/* Hash the upstream human-readable live-out dump, including its original
 * precision. This is a regression checksum, not a bitwise FP proof. */
static int pb_fprintf(FILE *stream, const char *format, ...)
{
    char buffer[768];
    va_list args;
    va_start(args, format);
    int count = vsnprintf(buffer, sizeof(buffer), format, args);
    va_end(args);
    if (count < 0 || (unsigned)count >= sizeof(buffer)) abort();
    for (int i = 0; i < count; ++i) {
        pb_hash ^= (unsigned char)buffer[i];
        pb_hash *= 16777619u;
    }
#ifdef CHASER_NATIVE
    if (pb_emit) fwrite(buffer, 1, (size_t)count, stream);
#else
    (void)stream;
    (void)pb_emit;
#endif
    return count;
}
#ifdef __clang__
#define PB_ANALYZE __attribute__((annotate("ape.analyze")))
#else
#define PB_ANALYZE
#endif
#define fprintf pb_fprintf
#endif
