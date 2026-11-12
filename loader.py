import csv
import random
from dataclasses import dataclass, field
from pathlib import Path

from style import ORANGE, PADDING, RESET

APP_NAMES: list[str] = [
    "Firefox",
    "PDF Arranger",
    "GIMP",
    "Inkscape",
    "Papers",
    "Safari",
    "Xcode",
    "Notion",
    "Google Chrome",
    "Microsoft Word",
    "Microsoft Excel",
    "Microsoft Powerpoint",
    "Microsoft OneNote",
    "Visual Studio Code",
    "Whatsapp Desktop",
    "Spotify",
    "Canva",
    "Draw.io",
    "GeoGebra",
    "Trello",
    "Discord",
    "Zoom",
    "Ghostty",
    "VirtualBox",
    "Docker Desktop",
    "GitHub Desktop",
    "Git Bash",
]
APP_NAMES_ITER = iter(random.sample(APP_NAMES, len(APP_NAMES)))


@dataclass(frozen=True)
class ProcessSpec:
    pid: int
    size: int
    arrival_time: int
    burst_time: int
    name: str = field(default_factory=lambda: next(APP_NAMES_ITER))


def validate_specs(specs: list[ProcessSpec], size_limit: int) -> bool:
    errors: list[str] = []
    for spec in specs:
        if spec.size > size_limit:
            errors.append(f"P{spec.pid} es mayor a la memoria ({size_limit})")
        if spec.burst_time == 0:
            errors.append(f"P{spec.pid} tiene un tiempo de irrupción igual a cero")
        elif spec.burst_time < 0:
            errors.append(f"P{spec.pid} tiene un tiempo de irrupción negativo")

    if errors:
        print()
        for err in errors:
            print(f"{ORANGE}{PADDING}ERROR: {err}{RESET}")
        return False
    else:
        return True


def read_specs_from_file(path: Path, amount: int = 8) -> list[ProcessSpec]:
    with open(path, "r", newline="", encoding="utf-8") as file:
        reader = csv.reader(file)
        next(reader)

        specs: list[ProcessSpec] = []
        for i, row in enumerate(reader, start=1):
            if i > amount:
                error = f"El archivo supera el límite de procesos. Se leyeron los primeros {amount}."
                print(f"{PADDING}{ORANGE}ERROR: {error}{RESET}")
                return specs

            pid, size, arrival, burst = map(int, row)
            specs.append(ProcessSpec(pid, size, arrival, burst))

        return specs
