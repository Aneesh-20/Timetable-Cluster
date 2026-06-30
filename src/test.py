from ortools.sat.python import cp_model
import pandas as pd

print("OR-Tools version:", cp_model.__name__)
print("Pandas version:", pd.__version__)
print("Setup complete! Ready to build the timetable optimizer.")