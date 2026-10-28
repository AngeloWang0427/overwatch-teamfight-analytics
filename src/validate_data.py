import csv
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parents[1] / "data/raw/teamfights_raw.csv"

with open(DATA_PATH, newline="", encoding="utf-8") as file:
    reader = csv.DictReader(file)
    fights = list(reader)

print(f"Total teamfights: {len(fights)}")

for fight in fights:
    start = int(fight["fight_start_sec"])
    end = int(fight["fight_end_sec"])

    print(
        f"Fight {fight['fight_id']}: "
        f"{end - start} seconds"
    )

