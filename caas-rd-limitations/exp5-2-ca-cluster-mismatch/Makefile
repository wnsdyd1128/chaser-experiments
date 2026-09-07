# RTEMS/GR740 build of the exp5-2 placement comparison, measured under laysim.
# One binary holds one case; tools/run_exp5_2_sweep.sh rebuilds with EXP5C_DEFS
# to walk the cases.
APP = $(BUILDDIR)/exp5_2_ca_cluster_mismatch

APP_C_FILES  = init.c
APP_C_FILES += cluster_comparison.c
APP_C_FILES += exp5c_placement.c
APP_C_FILES += exp5c_workload.c
APP_OBJS = $(APP_C_FILES:%.c=$(BUILDDIR)/%.o)
APP_DEPS = $(APP_C_FILES:%.c=$(BUILDDIR)/%.d)

INCFLAGS += $(EXP5C_DEFS)

include ../../common.mk
