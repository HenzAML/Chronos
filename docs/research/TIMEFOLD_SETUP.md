# How to Get Timefold Working in Chronos

To run the instructor-constraints experiment **with** Timefold (so the comparison table includes a Timefold row), do the following.

---

## 1. Install JDK 17 or later

Timefold’s Python solver uses the JVM under the hood, so a JDK is required.

- **macOS (Homebrew):**
  ```bash
  brew install openjdk@17
  ```
  Then set `JAVA_HOME` (add to `~/.zshrc` or run in the terminal):
  ```bash
  export JAVA_HOME=$(/usr/libexec/java_home 2>/dev/null || echo "/opt/homebrew/opt/openjdk@17")
  ```

- **macOS (Adoptium):**  
  Download [Eclipse Temurin 17+](https://adoptium.net) and set `JAVA_HOME` to the JDK root.

- **Linux (e.g. Ubuntu):**
  ```bash
  sudo apt install openjdk-17-jdk
  export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
  ```

Verify:
```bash
java -version
echo $JAVA_HOME
```
You should see a 17+ version and a non-empty `JAVA_HOME`.

---

## 2. Python version

Use **Python 3.10, 3.11, or 3.12** (as per [Timefold Solver for Python](https://github.com/TimefoldAI/timefold-solver-python)).

```bash
python3 --version
```

---

## 3. Install Timefold Solver for Python

From your project directory (with your venv activated if you use one):

```bash
pip install git+https://github.com/TimefoldAI/timefold-solver-python.git
```

If you use `requirements.txt`, you can add:
```
# Timefold (optional; requires JDK 17+ and JAVA_HOME)
# timefold @ git+https://github.com/TimefoldAI/timefold-solver-python.git
```
Uncomment and run `pip install -r requirements.txt` when you want Timefold.

---

## 4. Run the experiment

```bash
python experiment_instructor_constraints.py
```

If Timefold is installed correctly and `JAVA_HOME` is set:

- The script will **not** print the “Timefold not installed” / install-instructions message.
- The results table will include a **Timefold Solver** row (scheduled, hard violations, soft score, time).

If Timefold is still skipped:

- Check the error message printed by the script (e.g. `_TIMEFOLD_ERROR`).
- Ensure `JAVA_HOME` is set in the **same** shell you use to run `python experiment_instructor_constraints.py`.
- Try importing in Python:
  ```bash
  python -c "import timefold.solver; print('Timefold OK')"
  ```
  If that fails, fix the reported error (missing JDK, wrong Python version, or install failure) before re-running the experiment.

---

## 5. Optional: PyPI package

If the project publishes a wheel on PyPI (e.g. `timefold`), you can try:

```bash
pip install timefold
```

Prefer the git install above if the docs or this project assume the latest GitHub API (e.g. `SolverConfig`, `constraint_provider`, `PlanningId`).

---

## Summary checklist

| Step | Action |
|------|--------|
| 1 | Install **JDK 17+** and set **`JAVA_HOME`** |
| 2 | Use **Python 3.10–3.12** |
| 3 | `pip install git+https://github.com/TimefoldAI/timefold-solver-python.git` |
| 4 | Run `python experiment_instructor_constraints.py` and confirm the Timefold row appears |

The bridge code is in `chronos_timefold.py`; the experiment uses it only when the Timefold import succeeds and then calls `run_timefold_solver()` for the same problem instance as OR-Tools, Greedy, Random, and Backtracking.
