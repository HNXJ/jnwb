# Event Codes and Onsets

After inspection, read one interval table with `jnwb.events` or select codes with
`jnwb.event_onsets`. Pass `table=` explicitly when several interval tables are present;
jnwb raises `AmbiguousIntervalTableError` rather than guessing.

Default `code_column="codes"` and `onset_column="start_time"`. Onsets are returned in
**seconds**, preserving table row order.

```bash
python examples/tutorials/02_event_codes_and_onsets.py
```

```python
--8<-- "examples/tutorials/02_event_codes_and_onsets.py"
```
