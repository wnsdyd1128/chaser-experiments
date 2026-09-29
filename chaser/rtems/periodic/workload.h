#include <stdint.h>
/** @brief Prepare workload state before workers start; per-job reset is optional. @return None. */
void workload_prepare(void);
extern uint32_t (*const workload_jobs[])(void);
extern const uint32_t workload_expected[];
