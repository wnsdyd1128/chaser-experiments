# RTEMS/GR740 build of the exp5 architecture comparison, measured under laysim.
# One binary holds one case; tools/run_exp5_sweep.sh rebuilds with EXP5_DEFS to
# walk the cases.
APP = $(BUILDDIR)/exp5_ca_arch_mismatch

APP_C_FILES  = init.c
APP_C_FILES += arch_comparison.c
APP_C_FILES += exp5_workload.c
APP_OBJS = $(APP_C_FILES:%.c=$(BUILDDIR)/%.o)
APP_DEPS = $(APP_C_FILES:%.c=$(BUILDDIR)/%.d)

INCFLAGS += $(EXP5_DEFS)

include ../../common.mk
