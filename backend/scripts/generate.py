"""Run the solver from the command line and print the outcome.

    python scripts/generate.py            # uses the saved constraint config
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

from app import create_app
from app.solver import generate_schedule

with create_app().app_context():
    s = generate_schedule()
    placed, left = len(s.assignments), len(s.unscheduled or [])
    print(f"schedule {s.id}: {s.status}, {placed}/{placed + left} classes placed, "
          f"soft score {s.soft_score}, {s.solve_seconds:.1f}s")
    if s.status == "failed":
        print(s.message)
    for u in s.unscheduled or []:
        print(f"  [{u['code']}] {u['message']}")
