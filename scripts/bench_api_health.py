"""Read-only bounded load against the API database health endpoint."""

import argparse
import asyncio
import time

import httpx


async def exercise(url: str, requests: int, concurrency: int) -> None:
    timings = []
    async with httpx.AsyncClient(timeout=10, trust_env=False) as client:

        async def request() -> float:
            started = time.perf_counter()
            response = await client.get(url)
            response.raise_for_status()
            if response.json() != {"status": "ok", "database": "connected"}:
                raise ValueError("unexpected database health response")
            return time.perf_counter() - started

        started = time.perf_counter()
        for offset in range(0, requests, concurrency):
            count = min(concurrency, requests - offset)
            timings.extend(await asyncio.gather(*(request() for _ in range(count))))
        elapsed = time.perf_counter() - started

    timings.sort()
    p95 = timings[int(len(timings) * 0.95) - 1] * 1000
    print(
        f"{requests} GET {url}: {elapsed:.2f}s, {requests / elapsed:.1f} req/s, "
        f"p95={p95:.1f}ms, errors=0"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--requests", type=int, default=320)
    parser.add_argument("--concurrency", type=int, default=16)
    args = parser.parse_args()
    if args.requests < 1 or args.concurrency < 1:
        parser.error("requests and concurrency must be positive")
    asyncio.run(exercise(args.url, args.requests, args.concurrency))


if __name__ == "__main__":
    main()
