# Native build. The RTEMS build (Makefile.rtems) measures time on the GR740;
# this one is measured from outside with cachegrind, so it does not use
# ../../common.mk.
BUILDDIR = b-native
APP = $(BUILDDIR)/mean_rd_sweep

CC ?= gcc
CFLAGS ?= -O1 -Wall -Wextra

all: $(APP)

$(BUILDDIR):
	mkdir -p $(BUILDDIR)

$(APP): mean_rd_sweep.c | $(BUILDDIR)
	$(CC) $(CFLAGS) -o $@ $<

clean:
	rm -rf $(BUILDDIR)

.PHONY: all clean
