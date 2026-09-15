#ifndef CHASER_WORKLOAD_H
#define CHASER_WORKLOAD_H

#define CHASER_SWEEPS 65537
#define CHASER_DISTINCT 8

/** @brief Update eight adjacent bytes per sweep. @return Nothing. */
void chaser_packed(void);
/** @brief Update eight separate L1 lines in different sets. @return Nothing. */
void chaser_spread(void);
/** @brief Update eight separate lines mapping to one GR740 L1 set. @return Nothing. */
void chaser_conflict(void);
/** @brief Check packed bytes after one job invocation. @return One on success. */
int chaser_check_packed(void);
/** @brief Check spread bytes after one job invocation. @return One on success. */
int chaser_check_spread(void);
/** @brief Check conflict bytes after one job invocation. @return One on success. */
int chaser_check_conflict(void);

#endif
