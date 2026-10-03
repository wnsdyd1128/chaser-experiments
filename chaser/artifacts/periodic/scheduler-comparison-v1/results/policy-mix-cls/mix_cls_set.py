"""The policy-mix task sets with CLS-keyed placements: does grouping by CLS match grouping by traffic?

The same 160 cases as mix_set (same factors, roles, budgets, levels and seeds), so every run
pairs with its policy-mix-v1 case. Placements: wfd (the build each case is checked against),
cg and ra-cg (placement_lib; the group is the low-CLS tasks, cls <= CLS_LOW by the planned
CLS). Only the group key differs from tg and ra-tg, so the two coincide wherever low CLS
and high traffic coincide (traffic as-is, or no low-CLS 32 KiB task) and differ in sets
whose low-CLS 32 KiB tasks have matched traffic.
"""

from mix_set import *  # noqa: F401,F403  (hl_run reads the design constants from this module)
from placement_lib import CLS_POLICIES

PLACEMENTS = ('wfd',) + CLS_POLICIES
