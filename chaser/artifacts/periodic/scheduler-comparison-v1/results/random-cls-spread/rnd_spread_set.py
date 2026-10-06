"""Random baseline on experiment 23's sets: CLS mean 0.6 and 0.9 with spread.

CLS mean 0.3 overloads the L2 under every placement and SD 0 has no CLS group, so those
cells are left out.

Same tasks, sets and seeds as clsspread_set; P runs on placement_lib's RANDOM_POLICIES (each task on
a uniformly drawn core, redrawn until every core is under CORE_CAP, drawn from the set's seed),
so every run pairs with experiment 23's results on the same set. wfd is built (not run) for
hl_run's isolated gate and pm_run's yarda pass. protocol_extra is the base design's.
"""
from clsspread_set import *  # noqa: F401,F403  the base design's constants, sets and configuration
from clsspread_set import HEAVINESS as _BASE_HEAVINESS
from placement_lib import RANDOM_POLICIES

HEAVINESS = tuple(h for h in _BASE_HEAVINESS if not h.startswith('cls30') and '-sd00-' not in h)
PLACEMENTS = ('wfd',) + RANDOM_POLICIES
