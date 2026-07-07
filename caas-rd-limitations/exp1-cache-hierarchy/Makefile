APP = $(BUILDDIR)/exp1_cache_hierarchy

APP_C_FILES  = init.c
APP_C_FILES += hierarchy_workload.c
APP_C_FILES += exp1_workload.c
APP_OBJS = $(APP_C_FILES:%.c=$(BUILDDIR)/%.o)
APP_DEPS = $(APP_C_FILES:%.c=$(BUILDDIR)/%.d)

include ../../common.mk
