# Intelligent Timetable Optimizer

A final year engineering capstone project that automatically generates
conflict-free school timetables using a Greedy Algorithm and a
Genetic Algorithm (DEAP), with a live Streamlit web dashboard.

---

## Problem statement

Creating a school timetable manually takes days and often results in
conflicts — teachers double-booked, rooms clashing, subjects unevenly
distributed. This project automates the entire process and generates
a perfect, conflict-free timetable in under 1 second.

---

## What this project does

- Takes school data as input — teachers, rooms, sections, subjects
- Applies constraint-based scheduling rules (no teacher clashes, no
  room double-booking, every subject taught the correct number of times)
- Generates a complete weekly timetable for all classes automatically
- Verifies the result with zero hard constraint violations
- Displays the timetable in a live interactive web dashboard
- Allows downloading any class timetable as a CSV file

---

## Results

| Metric | Value |
|--------|-------|
| Sections scheduled | 3 (Class 10A, 10B, 11A) |
| Total assignments generated | 60 |
| Hard constraint violations | 0 |
| Solve time | < 1 second |
| Algorithm used | Greedy + Genetic Algorithm |

**Hard constraints satisfied:**
- No teacher assigned to two classes at the same time
- No room double-booked at the same time
- No section given two subjects at the same time
- Every subject taught the exact number of periods per week

---

## Dashboard screenshots

### Home screen
The dashboard loads with a single "Generate Timetable" button.
Click it to generate a complete conflict-free timetable instantly.

### Results screen
After generation, the dashboard shows:
- Total assignments, hard violations, sections scheduled
- A green "PERFECT timetable — zero conflicts!" banner
- A dropdown to switch between class timetables
- A full table showing Day, Period, Subject, Teacher, Room
- A CSV download button for each class

---

## Tech stack

| Tool | Purpose |
|------|---------|
| Python 3.10 | Core programming language |
| DEAP | Genetic Algorithm library |
| Streamlit | Web dashboard |
| pandas | Data manipulation |
| OR-Tools | Integer Linear Programming (research) |

---

## Project structure

---

## How to run

### Step 1 — Clone the repository

```bash
git clone https://github.com/YOURUSERNAME/timetable-optimizer.git
cd timetable-optimizer
```

### Step 2 — Create virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### Step 3 — Install dependencies

```bash
pip install -r requirements.txt
```

### Step 4 — Run the command line solver

```bash
python3 src/run_solver.py
```

### Step 5 — Launch the web dashboard

```bash
streamlit run dashboard/app.py
```

Open your browser at `http://localhost:8501` and click
**Generate Timetable**.

---

## How it works

### Greedy solver
The greedy solver assigns subjects one by one. For each subject in
each section, it finds an eligible teacher, an available room, and
a free time slot where no clashes occur. It fills all 60 periods
across 3 classes in under 1 second with zero violations.

### Genetic Algorithm solver
The GA solver encodes each timetable as a chromosome — a list of
integers where each integer represents a (teacher, room, day, period)
assignment. A population of 100 random timetables evolves over 300
generations using tournament selection, two-point crossover, and
uniform integer mutation. The fitness function penalises hard
violations (100 points each) and soft violations (10 points each).
The best individual after 300 generations is decoded into the
final timetable.

### Constraint checking
After generation, every timetable is verified by the constraint
checker which scans all pairs of assignments and flags any:
- Teacher clashes (same teacher, same time slot)
- Section clashes (same class, same time slot)
- Room clashes (same room, same time slot)

---

## Algorithms comparison

| Algorithm | Approach | Speed | Optimality |
|-----------|----------|-------|------------|
| Greedy | Assign one by one | < 1 second | Good |
| Genetic Algorithm | Evolve population | 30–60 seconds | Near-optimal |
| ILP (OR-Tools) | Mathematical solver | Variable | Optimal |

---

## Future work

- Real school data integration via Excel upload
- Teacher preference weighting in soft constraints
- Room capacity enforcement
- Web-based admin panel for managing school data
- Export to PDF formatted timetable
- Multi-week scheduling support

---

## Author

**Aneesh Naren**
Final Year B.Tech.Computer Science
Capstone Project — Data Analytics
2025–2026