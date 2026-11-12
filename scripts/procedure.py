"""Run ordered tasks with the shared model/executor/goal components."""
from pathlib import Path
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from household_agents.procedure_cli import main


if __name__ == '__main__':
    main()
