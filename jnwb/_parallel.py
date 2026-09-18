"""Shared CPU parallelism, with results that do not depend on how many workers ran.

Private module.

Two rules hold everywhere `n_jobs` appears in this library:

**The default is 1.** A library that saturates every core by default fights the caller's
own pool, and inside an outer `Parallel` or a batch scheduler it oversubscribes the
machine. Callers opt in.

**Results are independent of `n_jobs`.** Any parallel loop that consumes randomness
draws its seeds up front, one per iteration, from the caller's generator via
:func:`spawn_seeds`. Iteration *k* gets the same seed whether one worker ran or twelve,
so `n_jobs` is a speed knob and never changes a number. Advancing a single shared
generator inside the loop would make the output depend on scheduling order.
"""

from __future__ import annotations

import os
from typing import Callable, Iterable, List, Optional, Sequence

import numpy as np

__all__ = ["resolve_n_jobs", "spawn_seeds", "parallel_map"]


def resolve_n_jobs(n_jobs: Optional[int]) -> int:
    """Turn an `n_jobs` request into a worker count.

    ``None`` and ``1`` mean serial. ``-1`` means every CPU; ``-2`` all but one, matching
    joblib's negative convention. Values below ``-os.cpu_count()`` clamp to 1.
    """
    if n_jobs is None:
        return 1
    n_jobs = int(n_jobs)
    if n_jobs > 0:
        return n_jobs
    if n_jobs == 0:
        raise ValueError("n_jobs=0 is undefined; use 1 for serial or -1 for all CPUs")
    return max(1, (os.cpu_count() or 1) + 1 + n_jobs)


def spawn_seeds(rng: np.random.Generator, n: int) -> List[np.random.SeedSequence]:
    """Draw `n` independent child seed sequences from `rng`.

    Each element seeds one iteration, so the iteration's randomness is fixed before any
    worker starts. Deriving them from ``rng`` keeps the whole thing reproducible from the
    caller's seed.
    """
    entropy = int(rng.integers(0, 2**63 - 1))
    return list(np.random.SeedSequence(entropy).spawn(int(n)))


def parallel_map(
    fn: Callable,
    items: Sequence,
    n_jobs: Optional[int] = 1,
    *,
    prefer: Optional[str] = None,
    chunks_per_worker: int = 4,
) -> List:
    """Map `fn` over `items`, in parallel when asked and when joblib is installed.

    Work is dispatched in **chunks**, not one item at a time. Per-item dispatch is what
    makes naive parallelism lose: for a permutation loop with ~1 ms iterations, measured
    here, one-item-per-task ran 0.03x -- thirty times *slower* than serial -- because
    process startup and pickling dominated. Chunking the same loop into 4 batches per
    worker turned that into 4.2x faster.

    Parallelism only pays when the total serial work exceeds roughly **five seconds**,
    and the reason is not joblib. Spinning up 24 workers for a callable that closes over
    nothing takes 0.77 s; doing it for a callable the workers must import this package to
    unpickle takes 4.47 s, because each worker pays `import jnwb` -- 1.79 s in a fresh
    interpreter -- before it can run anything. Every parallel call site in this library
    passes such a callable, so several seconds is the real floor for the first parallel
    call in a process; the figures here were measured on a contended machine and the
    absolute values move, the ordering does not. Later calls reuse the pool and cost about 0.04 s, which is why a benchmark
    that calls twice in one process makes the floor disappear. Below that, leave
    `n_jobs=1`.

    Falls back to a serial comprehension when joblib is missing, so parallelism is an
    optimisation rather than a dependency. Result order always matches `items`.

    Args:
        fn: Called with one element of `items`.
        items: Work units.
        n_jobs: See :func:`resolve_n_jobs`. Default 1 (serial).
        prefer: Passed to joblib, e.g. ``"threads"`` for work that releases the GIL.
        chunks_per_worker: Batches per worker. Higher balances uneven work better and
            costs more dispatches.
    """
    items = list(items)
    workers = resolve_n_jobs(n_jobs)
    if workers == 1 or len(items) <= 1:
        return [fn(item) for item in items]

    try:
        from joblib import Parallel, delayed
    except ImportError:
        return [fn(item) for item in items]

    n_chunks = max(1, min(len(items), workers * max(1, chunks_per_worker)))
    bounds = np.linspace(0, len(items), n_chunks + 1).astype(int)
    chunks = [items[bounds[i]:bounds[i + 1]] for i in range(n_chunks) if bounds[i + 1] > bounds[i]]

    def _run_chunk(chunk):
        return [fn(item) for item in chunk]

    results = Parallel(n_jobs=workers, prefer=prefer)(delayed(_run_chunk)(c) for c in chunks)
    return [value for chunk_result in results for value in chunk_result]
