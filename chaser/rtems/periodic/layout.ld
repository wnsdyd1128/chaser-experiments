SECTIONS { .chaser_data 0x01000000 (NOLOAD) : {
  KEEP(*(SORT_BY_NAME(.chaser_data.*)))
} > ram } INSERT BEFORE .bss;
ASSERT(SIZEOF(.chaser_data) <= 0x01000000, "workload data overflow")
