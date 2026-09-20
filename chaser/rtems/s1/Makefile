RTEMS_ROOT ?= /opt/rtems/6
PC = $(RTEMS_ROOT)/lib/pkgconfig/sparc-rtems6-gr740.pc
CC = $(RTEMS_ROOT)/bin/sparc-rtems6-gcc
# SOURCE, INIT, BUILD and PLUGIN are absolute snapshot paths supplied by the suite.
.PHONY: all
all: $(BUILD)/workload.exe $(BUILD)/workload_ape.json

$(BUILD):
	mkdir -p $@

$(BUILD)/workload.exe: $(SOURCE) $(INIT) $(lastword $(MAKEFILE_LIST)) | $(BUILD)
	$(CC) -O0 -g -Wall -Wextra $$(pkg-config --cflags $(PC)) -mcpu=leon3 -mfpu -mhard-float -ffunction-sections -fdata-sections $(INIT) $(SOURCE) -Wl,--gc-sections $$(pkg-config --libs $(PC)) -lrtemsbsp -lrtemscpu -lm -o $@

$(BUILD)/workload.ll: $(SOURCE) | $(BUILD)
	clang-14 -O0 -Xclang -disable-O0-optnone -g -emit-llvm -S $< -o $@

$(BUILD)/workload_ape.json: $(BUILD)/workload.ll $(PLUGIN)
	cd $(BUILD) && opt-14 -load-pass-plugin=$(PLUGIN) '-passes=function(mem2reg),loop-simplify,loop-annotated-trace' workload.ll -o /dev/null
