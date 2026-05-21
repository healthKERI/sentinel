# Parallel Execution Optimizations

## Overview

The Receiptor and Sentinel classes have been optimized to use `asyncio.gather()` for parallel witness queries, significantly improving performance when dealing with multiple witnesses.

## Optimizations Implemented

### 1. Receiptor.receipt() - Parallel Receipt Collection

**Before:**
- Sequential queries to each witness
- Each witness waited for individually
- Total time = sum of all witness response times

**After:**
- All witnesses queried simultaneously using `asyncio.gather()`
- Added helper method `_query_witness_for_receipt()` for parallel execution
- Total time ≈ max(witness response times)

**Performance Impact:**
- **3 witnesses**: ~3x faster
- **10 witnesses**: ~10x faster
- **100 witnesses**: ~100x faster

**Code Example:**
```python
# Query all witnesses in parallel
results = await asyncio.gather(
    *[self._query_witness_for_receipt(hab, wit, msg, auths) for wit in wits],
    return_exceptions=True
)
```

### 2. Receiptor.receipt() - Parallel Receipt Propagation

**Before:**
- Sequential propagation to each witness
- Each propagation waited for individually

**After:**
- All propagations executed simultaneously
- Added helper method `_propagate_receipt_to_witness()`
- Uses `asyncio.gather()` for parallel execution

**Performance Impact:**
- Similar to receipt collection: ~Nx faster for N witnesses

### 3. Receiptor.catchup() - Batched KEL Transmission

**Before:**
- Sequential transmission of each KEL event
- One event at a time to witness

**After:**
- Events sent in configurable batches (default: 10 events/batch)
- Each batch sent in parallel using `asyncio.gather()`
- Batching maintains reasonable resource usage while improving speed

**Performance Impact:**
- **100 events, batch_size=10**: ~10x faster
- **1000 events, batch_size=10**: ~10x faster
- Configurable batch size for tuning

**Code Example:**
```python
# Send events in batches
for i in range(0, len(events), batch_size):
    batch = events[i:i + batch_size]
    tasks = [self._post_cesr(url, bytearray(fmsg), headers) for fmsg in batch]
    await asyncio.gather(*tasks, return_exceptions=True)
```

### 4. Sentinel.watch() - Parallel Witness State Queries

**Before:**
- Sequential key state notice (KSN) queries to each witness
- Each witness processed one at a time

**After:**
- All witnesses queried simultaneously
- Added helper method `_query_single_witness()`
- Uses `asyncio.gather()` for parallel execution

**Performance Impact:**
- For watching AIDs with N witnesses: ~Nx faster witness queries
- Dramatically improves watcher responsiveness

**Code Example:**
```python
# Query all witnesses in parallel
results = await asyncio.gather(
    *[self._query_single_witness(wit, kever, receiptor, queryTimestamp)
      for wit in kever.wits],
    return_exceptions=True
)
```

## Error Handling

All parallel operations use `return_exceptions=True` to ensure:
- One failed witness doesn't block others
- Exceptions are caught and logged
- Partial success is supported (some witnesses succeed, others fail)

**Example:**
```python
results = await asyncio.gather(*tasks, return_exceptions=True)
for result in results:
    if isinstance(result, Exception):
        logger.error(f"Exception during operation: {result}")
        continue
    # Process successful result
```

## Configuration

### Catchup Batch Size

The `catchup()` method accepts a configurable `batch_size` parameter:

```python
# Default: 10 events per batch
await receiptor.catchup(pre, wit)

# Custom batch size for fine-tuning
await receiptor.catchup(pre, wit, batch_size=20)
```

**Tuning Guidelines:**
- **Small batch (5-10)**: Lower memory usage, more granular progress
- **Medium batch (10-20)**: Good balance for most cases (default)
- **Large batch (50+)**: Maximum speed, higher memory usage

## Logging

Enhanced logging provides visibility into parallel operations:

```python
logger.debug(f"Querying {len(wits)} witnesses in parallel for receipts")
logger.debug(f"Received {len(rcts)} receipts from {len(wits)} witnesses")
logger.debug(f"Propagating receipts to {len(propagation_tasks)} witnesses in parallel")
logger.debug(f"Catching up witness {wit} with {len(events)} events in batches of {batch_size}")
```

## Performance Benchmarks

### Scenario: 10 Witnesses, 100ms Response Time Each

| Operation | Before (Sequential) | After (Parallel) | Speedup |
|-----------|---------------------|------------------|---------|
| Receipt Collection | 1000ms | ~100ms | ~10x |
| Receipt Propagation | 1000ms | ~100ms | ~10x |
| Catchup (100 events) | 10000ms | ~1000ms | ~10x |
| Witness State Query | 1000ms | ~100ms | ~10x |

### Scenario: 3 Witnesses, 50ms Response Time Each

| Operation | Before (Sequential) | After (Parallel) | Speedup |
|-----------|---------------------|------------------|---------|
| Receipt Collection | 150ms | ~50ms | ~3x |
| Receipt Propagation | 150ms | ~50ms | ~3x |
| Catchup (50 events) | 2500ms | ~250ms | ~10x |
| Witness State Query | 150ms | ~50ms | ~3x |

## Implementation Details

### Helper Methods Added

**Receiptor class:**
- `_query_witness_for_receipt(hab, wit, msg, auths)`: Query single witness for receipt
- `_propagate_receipt_to_witness(hab, wit, msg_bytes)`: Propagate receipt to single witness

**Sentinel class:**
- `_query_single_witness(wit, kever, receiptor, queryTimestamp)`: Query single witness for key state

### Backward Compatibility

All optimizations are **100% backward compatible**:
- Public API unchanged
- Method signatures unchanged (except optional `batch_size` parameter added to `catchup()`)
- Return values unchanged
- Error handling behavior unchanged

## Testing Recommendations

### Unit Tests

```python
import pytest
from unittest.mock import AsyncMock, MagicMock

@pytest.mark.asyncio
async def test_parallel_receipt_collection():
    """Test that receipts are collected in parallel"""
    receiptor = Receiptor(hby=mock_hby)

    # Mock witnesses
    wits = ['wit1', 'wit2', 'wit3']

    # Verify parallel execution
    with patch.object(receiptor, '_query_witness_for_receipt') as mock_query:
        mock_query.return_value = ('wit', b'receipt')

        result = await receiptor.receipt('pre', sn=0)

        # Verify all witnesses were queried
        assert mock_query.call_count == len(wits)
```

### Integration Tests

```python
@pytest.mark.asyncio
async def test_catchup_performance():
    """Test that catchup uses batching for performance"""
    receiptor = Receiptor(hby=real_hby)

    start_time = time.time()
    await receiptor.catchup(pre, wit, batch_size=10)
    elapsed = time.time() - start_time

    # Verify significant speedup vs sequential
    assert elapsed < expected_sequential_time / 5
```

## Monitoring

Track parallel operation performance:

```python
import time

# Before receipt collection
start = time.time()
result = await receiptor.receipt(pre, sn)
elapsed = time.time() - start

logger.info(f"Receipt collection took {elapsed:.3f}s for {len(result)} witnesses")
```

## Future Optimizations

Potential further improvements:

1. **Adaptive Batch Sizing**: Automatically adjust batch size based on network conditions
2. **Connection Pooling**: Reuse HTTP connections across multiple requests
3. **Request Prioritization**: Query faster witnesses first, slower ones later
4. **Caching**: Cache witness responses for short periods
5. **Rate Limiting**: Add configurable rate limits to prevent overwhelming witnesses

## Conclusion

The parallel execution optimizations provide significant performance improvements:
- **~Nx speedup** for N witnesses in most operations
- No breaking changes to existing code
- Improved error handling with exception isolation
- Better resource utilization
- Enhanced logging for observability

These optimizations make the sentinel watcher much more responsive and efficient when monitoring AIDs with multiple witnesses.
