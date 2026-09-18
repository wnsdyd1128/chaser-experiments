YARDA_DIR ?= /workspace/Yet-Another-Reuse-Distance-Analyzer
YARDA_CPP ?= $(CURDIR)/build/yarda/backend/yarda_cpp
PLUGIN ?= $(CURDIR)/build/yarda/libMemoryAccessPatterns.so
RTEMS_ROOT ?= /opt/rtems/6
PC = $(RTEMS_ROOT)/lib/pkgconfig/sparc-rtems6-gr740.pc
CC = $(RTEMS_ROOT)/bin/sparc-rtems6-gcc
BUILD = build
EXPORTS = ../../exports
CASES = packed spread conflict

# Keep analysis inputs for the provenance hash checks after a fresh build.
.SECONDARY: $(addprefix $(BUILD)/, $(addsuffix .ape.json, $(CASES)))

.PHONY: all analyze hierarchy $(addprefix run-, $(CASES))
all: $(addprefix $(BUILD)/, $(addsuffix .exe, $(CASES)))

$(BUILD):
	mkdir -p $@

$(EXPORTS):
	mkdir -p $@

$(addprefix $(BUILD)/, $(addsuffix .exe, $(CASES))): $(BUILD)/%.exe: init.c workload.c workload.h Makefile | $(BUILD)
	$(CC) -O0 -g -Wall -Wextra $$(pkg-config --cflags $(PC)) -mcpu=leon3 -mfpu -mhard-float -ffunction-sections -fdata-sections -DCHASER_NAME='"$*"' -DCHASER_JOB=chaser_$* -DCHASER_CHECK=chaser_check_$* init.c workload.c -Wl,--gc-sections $$(pkg-config --libs $(PC)) -lrtemsbsp -lrtemscpu -lm -o $@

$(BUILD)/workload.ll: workload.c workload.h | $(BUILD)
	clang-14 -O0 -Xclang -disable-O0-optnone -g -emit-llvm -S workload.c -o $@

$(BUILD)/workload_ape.json: $(BUILD)/workload.ll $(PLUGIN)
	cd $(BUILD) && opt-14 -load-pass-plugin=$(PLUGIN) '-passes=function(mem2reg),loop-simplify,loop-annotated-trace' workload.ll -o /dev/null

analyze: $(BUILD)/workload_ape.json | $(EXPORTS)
	$(YARDA_CPP) $< --mode unroll --granularity element --max-cumulative-loop-iterations 2000000 --export $(EXPORTS)/element.rdh.json
	$(YARDA_CPP) $< --mode unroll --granularity cache-line --cache cache.yaml --max-cumulative-loop-iterations 2000000 --export $(EXPORTS)/line.rdh.json

$(addprefix run-, $(CASES)): run-%: $(BUILD)/%.exe
	/opt/laysim-gr740/laysim-gr740-cli -r -core0 $<

$(BUILD)/%.ape.json: $(BUILD)/workload_ape.json ../../tools/select_baseline_ape.py
	python3 ../../tools/select_baseline_ape.py $< $* $@

hierarchy: $(addprefix $(EXPORTS)/, $(addsuffix .csrd.json, $(CASES)))

$(EXPORTS)/%.csrd.json: $(BUILD)/%.ape.json $(BUILD)/%.exe cache.yaml $(YARDA_CPP) Makefile | $(EXPORTS)
	$(YARDA_CPP) $< --analysis hierarchy-rd --elf $(BUILD)/$*.exe --cache cache.yaml --max-source-accesses 1100000 --export $@
