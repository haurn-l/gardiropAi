"""One optional release of unused Torch allocator cache after neural warmup."""

import time

POLICY_ID = "release-unused-cuda-cache-after-warmup-v1"


def release_warmup_cache(*, enabled: bool, device: str, torch_module=None):
    """Called once inside the startup GPU slot, never in the photograph path.

    Live model tensors and native TensorRT allocations are not freed by empty_cache.
    Later PyTorch shapes may grow the cache again. The difference reserved-allocated
    is not a guarantee that every inactive split block is releasable.
    """
    result = {
        "policy": POLICY_ID,
        "requested": enabled,
        "applied": False,
        "scope": "Startup only. Torch allocator counters exclude native TensorRT memory. Peak startup demand is unchanged.",
    }
    if not enabled or device != "cuda":
        result["reason"] = "disabled" if not enabled else "cpu_runtime"
        return result
    if torch_module is None:
        import torch as torch_module
    cuda = torch_module.cuda
    if not cuda.is_initialized():
        raise RuntimeError("Warmup cache release requires the already initialized CUDA runtime.")
    started = time.perf_counter()
    cuda.synchronize()
    before = {"allocated_bytes": cuda.memory_allocated(), "reserved_bytes": cuda.memory_reserved()}
    cuda.empty_cache()
    after = {"allocated_bytes": cuda.memory_allocated(), "reserved_bytes": cuda.memory_reserved()}
    if after["allocated_bytes"] != before["allocated_bytes"]:
        raise RuntimeError("Active Torch allocations changed during isolated warmup cache release.")
    result.update(
        applied=True,
        before=before,
        after=after,
        released_reserved_mib=(before["reserved_bytes"] - after["reserved_bytes"]) / 1024**2,
        active_allocations_unchanged=True,
        elapsed_seconds=time.perf_counter() - started,
    )
    return result
