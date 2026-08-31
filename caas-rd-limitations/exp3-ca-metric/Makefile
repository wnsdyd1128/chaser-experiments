# Native build. exp3 is measured with cachegrind on the host, not on the GR740
# target, so it does not use ../../common.mk.
BUILDDIR = b-native
APP = $(BUILDDIR)/ca_sweep

CC ?= gcc
CFLAGS ?= -O1 -Wall -Wextra

all: $(APP)

$(BUILDDIR):
	mkdir -p $(BUILDDIR)

$(APP): ca_sweep.c | $(BUILDDIR)
	$(CC) $(CFLAGS) -o $@ $<

clean:
	rm -rf $(BUILDDIR)

.PHONY: all clean
