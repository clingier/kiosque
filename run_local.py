"""
run_local.py — Run the Kiosque collector locally for testing.

Writes output to ./output/raw/feeds/YYYY-MM-DD/ instead of ADLS.
Usage: python run_local.py [--sources config/sources.yaml] [--limit N]
"""

import argparse
import json
import logging
import sys
from pathlib import Path

# Ensure functions/ is on the path
sys.path.insert(0, str(Path(__file__).parent / "functions"))

from collector import run_collection
from storage import StorageWriter


def main():
    parser = argparse.ArgumentParser(description="Run Kiosque collector locally")
    parser.add_argument(
        "--sources",
        default=str(Path(__file__).parent / "config" / "sources.yaml"),
        help="Path to sources.yaml (default: config/sources.yaml)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Limit to first N sources (0 = all, useful for quick test)",
    )
    parser.add_argument(
        "--output",
        default="./output",
        help="Output directory (default: ./output)",
    )
    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    # Force local storage mode
    writer = StorageWriter(mode="local", local_dir=args.output)

    # If --limit is set, patch load_sources to truncate
    if args.limit > 0:
        import collector as collector_module
        original_load = collector_module.load_sources

        def limited_load(config_path=None):
            sources = original_load(config_path or args.sources)
            logging.info("Limiting to first %d sources (out of %d)", args.limit, len(sources))
            return sources[: args.limit]

        collector_module.load_sources = limited_load

    print(f"\n🗞️  Kiosque — Local Collection Run")
    print(f"   Sources: {args.sources}")
    print(f"   Output:  {args.output}")
    if args.limit:
        print(f"   Limit:   first {args.limit} sources")
    print()

    report = run_collection(config_path=args.sources, writer=writer)

    # Print summary
    print(f"\n{'='*60}")
    print(f"📊 Collection Report")
    print(f"{'='*60}")
    print(f"   Date:           {report['date']}")
    print(f"   Duration:       {report['duration_seconds']}s")
    print(f"   Total sources:  {report['total_sources']}")
    print(f"   ✅ Success:     {report['success_count']}")
    print(f"   ❌ Failures:    {report['failure_count']}")
    print(f"   📰 Articles:    {report['total_articles']}")
    print()

    # Print per-source details
    ok_sources = [s for s in report["sources"] if s["status"] == "ok"]
    err_sources = [s for s in report["sources"] if s["status"] == "error"]

    if ok_sources:
        print(f"✅ Successful sources ({len(ok_sources)}):")
        for s in sorted(ok_sources, key=lambda x: x["article_count"], reverse=True):
            print(f"   {s['slug']:30s} {s['source_method']:8s} {s['article_count']:4d} articles  ({s['duration_ms']}ms)")

    if err_sources:
        print(f"\n❌ Failed sources ({len(err_sources)}):")
        for s in err_sources:
            print(f"   {s['slug']:30s} {s.get('error', 'Unknown error')}")

    print(f"\n📁 Output written to: {args.output}/raw/feeds/{report['date']}/")


if __name__ == "__main__":
    main()
