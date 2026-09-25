"""Controlled load-only S1 inputs for the baseline 32-byte, four-way hierarchy."""


def cases() -> list[dict]:
    catalog = [{'id': 'packed_8', 'family': 'layout', 'distinct': 8, 'stride': 1}]
    for distinct in (3, 4, 5, 8):
        for layout, stride in (('spread', 32), ('conflict', 4096)):
            catalog.append({'id': f'{layout}_{distinct}', 'family': 'associativity',
                            'distinct': distinct, 'stride': stride})
    for distinct in (256, 448, 511, 512, 513, 576, 1024, 32768,
                     61440, 65535, 65536, 65537, 69632, 73728):
        catalog.append({'id': f'capacity_{distinct}', 'family': 'capacity',
                        'distinct': distinct, 'stride': 32})
    for shape in ('uniform', 'mixed'):
        catalog.append({'id': f'mean_{shape}', 'family': 'distribution',
                        'distinct': 1024, 'stride': 32})
    return catalog


def access_count(case: dict, sweeps: int) -> int:
    if type(sweeps) is not int or not 2 <= sweeps <= 1000:
        raise ValueError('Sweeps must be an integer between 2 and 1000')
    if case['family'] == 'distribution':
        return 1024 + 2046 * (sweeps - 1)
    return case['distinct'] * sweeps


def source_text(case: dict, sweeps: int) -> str:
    """Emit literal loop bounds shared by Clang extraction and the SPARC build.

    Both mean cases have 1024 cold lines and 2046*(sweeps-1) finite reuses.
    Uniform revisits a 512-line cycle then touches 512 new lines once. Mixed
    revisits one line and a disjoint 1023-line cycle equally often. Both finite
    means are 511; cold population, total accesses and footprint also match.
    Preparation is outside the annotated region; its warm-cache effects are
    not part of the cold abstract model.
    """
    total = access_count(case, sweeps)
    size = case['distinct'] * case['stride']
    if case['id'] == 'mean_mixed':
        body = f'''    for (int repeat = 0; repeat < {1023 * (sweeps - 1) + 1}; ++repeat)
        sum += data[0];
    for (int sweep = 0; sweep < {sweeps}; ++sweep)
        for (int i = 32; i < 32768; i += 32)
            sum += data[i];'''
    elif case['id'] == 'mean_uniform':
        full, remainder = divmod(512 + 2046 * (sweeps - 1), 512)
        body = f'''    for (int sweep = 0; sweep < {full}; ++sweep)
        for (int i = 0; i < 16384; i += 32)
            sum += data[i];
    for (int i = 0; i < {remainder * 32}; i += 32)
        sum += data[i];
    for (int i = 16384; i < 32768; i += 32)
        sum += data[i];'''
    else:
        body = f'''    for (int sweep = 0; sweep < {sweeps}; ++sweep)
        for (int i = 0; i < {size}; i += {case['stride']})
            sum += data[i];'''
    return f'''/* Generated S1 case: {case['id']}; sweeps parameter: {sweeps}. */
#include <stdint.h>
#ifdef __clang__
#define ANALYZE __attribute__((annotate("ape.analyze")))
#else
#define ANALYZE
#endif
static volatile uint8_t data[{size}] __attribute__((aligned(4096)));

/** @brief Initialize data outside the analyzed region. @return None. */
void s1_prepare(void)
{{
    for (int i = 0; i < {size}; ++i)
        data[i] = 1;
}}

/** @brief Provide the generated load-count checksum. @return Expected sum. */
uint32_t s1_expected(void) {{ return {total}; }}

/** @brief Read initialized data without a global sink. @return Accumulated sum. */
ANALYZE uint32_t chaser_s1(void)
{{
    uint32_t sum = 0;
{body}
    return sum;
}}
'''
