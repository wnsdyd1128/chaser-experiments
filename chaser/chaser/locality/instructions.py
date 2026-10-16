"""Static per-job IR instruction counts from an APE map extraction (YARDA's workload_ape.json).

Each function's ir_instructions lists basic blocks with a static execution count per call and
their opcodes; a block's calls to functions in the same extraction (the inlined kernels) add the
callee's counts once per execution. Calls outside the extraction (opaque library calls) add
nothing beyond their own call opcode. Counts are LLVM IR instructions of the analysis build
(clang -O0 with mem2reg), a relative measure of work, not target machine instructions. YARDA gives no
block counts for a function whose loop trip counts are not constant (status unsupported, e.g. a
triangular loop); a job reaching one has no count.
"""

from functools import cache


def job_ir_counts(ape: dict, root: str) -> tuple[int, int] | None:
    """(IR instructions, loads + stores) of one call of root, e.g. task_job_<task_id>; None when a reached
    function has no block counts."""
    functions = {f['function']: f['ir_instructions'].get('blocks') for f in ape['functions']}
    if root not in functions:
        raise ValueError(f'{root} is not in the APE extraction')

    @cache
    def per_call(name: str) -> tuple[int, int] | None:
        if functions[name] is None:
            return None
        instructions = memory = 0
        for block in functions[name]:
            runs, opcodes = block['executions'], block['opcodes']
            instructions += runs * sum(opcodes.values())
            memory += runs * (opcodes.get('load', 0) + opcodes.get('store', 0))
            for call in block['calls']:
                if call['callee'] in functions:
                    callee = per_call(call['callee'])
                    if callee is None:
                        return None
                    instructions += runs * callee[0]
                    memory += runs * callee[1]
        return instructions, memory

    return per_call(root)
