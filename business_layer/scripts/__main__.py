"""List the persistent walkthrough steps; run each module separately."""
from pathlib import Path


def main():
    print("Run one script at a time, then inspect your Docker database.")
    print("Connection: HOST_DATABASE_URL from .env; successful writes are COMMITTED.\n")
    for path in sorted(Path(__file__).parent.glob("step_*.py")):
        print(f".venv/bin/python -m business_layer.scripts.{path.stem}")
    print("\nOptional on every command: --model-key my_walkthrough")
    print("Details: business_layer/scripts/README.md")


if __name__ == "__main__":
    main()
