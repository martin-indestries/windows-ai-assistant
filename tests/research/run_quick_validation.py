"""
Quick validation script for research pipeline.

Runs a real research query (not mocked) to validate the full pipeline.
"""

import logging
import sys
from pathlib import Path

# Add src to path before imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from spectral.research import ResearchOrchestrator  # noqa: E402

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


def main():
    """Run quick validation."""
    logger.info("=" * 60)
    logger.info("Research Pipeline Quick Validation")
    logger.info("=" * 60)

    query = "How to install Python on Windows"
    logger.info(f"\nQuery: {query}\n")

    orchestrator = ResearchOrchestrator(enable_playwright=False)

    logger.info("Starting research...")
    pack = orchestrator.run_research(query, max_pages=3)

    logger.info("\n" + "=" * 60)
    logger.info("RESULTS")
    logger.info("=" * 60)

    print(f"\nGoal: {pack.goal}")
    print(f"Confidence: {pack.confidence:.0%}")
    print(f"Sources: {len(pack.sources)}")
    print(f"Steps: {len(pack.steps)}")
    print(f"Commands: {len(pack.commands)}")

    if pack.steps:
        print("\nSteps:")
        for i, step in enumerate(pack.steps, start=1):
            print(f"  {i}. {step.get('title', 'Untitled')}")

    if pack.commands:
        print("\nCommands:")
        for cmd in pack.commands[:3]:
            print(f"  - {cmd.get('command_text', 'N/A')}")

    if pack.sources:
        print("\nSources:")
        for i, source in enumerate(pack.sources[:3], start=1):
            print(f"  [{i}] {source.title}")
            print(f"      {source.url}")

    logger.info("\n" + "=" * 60)
    logger.info("Validation complete!")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
