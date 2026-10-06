"""Random baseline on experiment 20's sets: the 25 % memory cell (50 % fails everywhere).

Same tasks, sets and seeds as taskcount_set; P runs on placement_lib's RANDOM_POLICIES (each task on
a uniformly drawn core, redrawn until every core is under CORE_CAP, drawn from the set's seed),
so every run pairs with experiment 20's results on the same set. wfd is built (not run) for
hl_run's isolated gate and pm_run's yarda pass. protocol_extra is the base design's.
"""
from taskcount_set import *  # noqa: F401,F403  the base design's constants, sets and configuration
from taskcount_set import HEAVINESS as _BASE_HEAVINESS
from placement_lib import RANDOM_POLICIES

HEAVINESS = ('mem25',)
PLACEMENTS = ('wfd',) + RANDOM_POLICIES
