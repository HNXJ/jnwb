# Run Records and the Result Cache

`jnwb.ExecutionRecord` names what ran where: the device string the backend resolved and the worker count the parallel loop ran with. A caller builds one beside a result and reads it back later. The record carries no behavior and selects nothing; two runs that differ only in these fields compute the same numbers.

Its signature is `ExecutionRecord(device, n_jobs)`; both fields are required. The device field takes any string the backend resolves. A count below 1 raises `ValueError`, and a non-string device raises `TypeError`.

## Keys

`jnwb.cache_key` builds one hex key for one operation from its name, its inputs and its parameters, mixed with the jnwb version. Arrays enter the hash as dtype, shape and raw bytes, and mappings enter as canonical JSON with sorted keys, so mapping order never moves the key. A version change moves every key, so a key from one version never reads a value another version wrote.

Its signature is `cache_key(name, inputs, params)`. Inputs and parameters accept arrays, scalars, dicts, lists and tuples; a value with no canonical form raises `TypeError` naming its type.

## The store

`jnwb.cache_store` saves one value under one key in a caller-chosen directory and returns the file path. Entries are `.npz` archives written with `allow_pickle=False`; each one carries the key and the jnwb version it was written with. The write lands atomically: bytes go to a temporary sibling file that is flushed and synced, then renamed over the target, so a reader never sees a half-written entry.

Its signature is `cache_store(cache_dir, key, value)`. Values accept arrays, scalars, dicts, lists and tuples; anything else raises `TypeError`. A key that could escape the directory raises `ValueError`.

## Loading and clearing

`jnwb.cache_load` reads the value stored under one key in one directory, or None on a miss. Its signature is `cache_load(cache_dir, key)`.

| Miss | What loads |
|---|---|
| no entry under the key | None |
| the stored key differs from the requested one | None |
| the stored version differs from the running jnwb version | None |
| the entry matches this version and reads cleanly | the stored value |

A present entry from this version that cannot be read raises, so a corrupt file never reads as a value.

`jnwb.cache_clear` removes the entries `cache_store` wrote directly under one directory and counts the removals. Its signature is `cache_clear(cache_dir)`. Other files stay, other `.npz` archives included.
