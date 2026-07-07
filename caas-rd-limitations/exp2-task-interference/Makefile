APP = $(BUILDDIR)/exp2_task_interference

APP_C_FILES  = init.c
APP_C_FILES += interference_workload.c
APP_C_FILES += exp2_workload.c
APP_OBJS = $(APP_C_FILES:%.c=$(BUILDDIR)/%.o)
APP_DEPS = $(APP_C_FILES:%.c=$(BUILDDIR)/%.d)

INCFLAGS += $(EXP2_DEFS)

include ../../common.mk
