from textwrap import wrap
from typing import Any

from loader import ProcessSpec
from simulador import (
    MAX_MULTIPROGRAMMING,
    PCB,
    Event,
    EventTy,
    Gap,
    Partition,
    ProcessState,
)
from style import (
    ANSI_PATTERN,
    BADGE,
    BLOCK,
    BLUE,
    BOLD,
    BORDER,
    CLEAR,
    DARK_TEXT,
    FREE_STYLE,
    GRAY,
    GREEN,
    LAVENDER,
    ORANGE,
    OS_STYLE,
    PADDING,
    PROCESS_COLORS,
    RESET,
    TITLE_STYLE,
    TRACK,
    WHITE,
    YELLOW,
)

Report = dict[str, Any]

WIDTH = 120
TABLE_COLUMN_GAP = "  "

# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------


def clear() -> None:
    """Borra la pantalla y el historial de desplazamiento, y lleva el cursor al inicio."""
    print(CLEAR, end="", flush=True)


def await_user_input(action_message: str = "continuar") -> None:
    while input(f"{PADDING}Presioná {YELLOW}ENTER{RESET} para {action_message}") != "":
        pass


def print_loaded_specs(loaded: list[ProcessSpec]) -> None:
    """Imprime los procesos cargados desde el archivo, con los valores alineados a la derecha."""
    if not loaded:
        return

    pid_width = max(len(f"P{spec.pid}") for spec in loaded)
    name_width = max(len(spec.name) for spec in loaded)
    size_width = max(len(f"{spec.size}K") for spec in loaded)
    arrival_width = max(len(str(spec.arrival_time)) for spec in loaded)
    burst_width = max(len(f"{spec.burst_time}u") for spec in loaded)

    print(f"\n{PADDING}{GREEN}✓ {len(loaded)} proceso(s) cargado(s){RESET}\n")

    for spec in loaded:
        color = _process_color(spec.pid)
        badge_style = f"\033[48;5;{color}m{DARK_TEXT}{BOLD}"
        name_style = f"\033[38;5;{color}m{BOLD}"

        pid = f"P{spec.pid}".rjust(pid_width)
        name = spec.name.ljust(name_width)
        size = f"{spec.size}K".rjust(size_width)
        arrival = str(spec.arrival_time).rjust(arrival_width)
        burst = f"{spec.burst_time}u".rjust(burst_width)

        print(
            f"{PADDING}{badge_style} {pid} {RESET}"
            f"  {name_style}{name}{RESET}"
            f"   {GRAY}tamaño {WHITE}{size}"
            f"   {GRAY}arribo {WHITE}t={arrival}"
            f"   {GRAY}irrupción {WHITE}{burst}{RESET}"
        )


def draw_state(report: Report) -> None:
    _draw_heading(report)
    _draw_queues(report)
    _draw_memory(report)
    _draw_processes_and_events(report)


def draw_summary(report: Report) -> None:
    """Dibuja tiempos, rendimiento y la línea de vida reconstruida desde los eventos."""
    _print_box("TIEMPOS POR PROCESO", _final_process_rows(report))
    _print_box("RENDIMIENTO DEL SISTEMA", _final_system_rows(report))
    _print_box("LÍNEA DE VIDA DE LOS PROCESOS", _lifetime_rows(report))


# ---------------------------------------------------------------------------
# Utilidades de dibujo (puras: no dependen del reporte)
# ---------------------------------------------------------------------------


def _visible_len(text: str) -> int:
    """Largo del texto tal como se ve en pantalla (sin secuencias ANSI)."""
    return len(ANSI_PATTERN.sub("", text))


def _pad(text: str, width: int) -> str:
    """Rellena con espacios hasta `width` columnas visibles."""
    return text + " " * max(0, width - _visible_len(text))


def _center(text: str, width: int) -> str:
    """Centra texto plano (sin ANSI) en `width` columnas, truncándolo si no entra."""
    text = text[:width]
    left = (width - len(text)) // 2
    return " " * left + text + " " * (width - len(text) - left)


def _bar(value: int, total: int, width: int, color: str) -> str:
    """Barra de progreso: parte llena con `color`, parte vacía en gris oscuro."""
    ratio = min(value / total, 1) if total > 0 else 0
    filled = round(width * ratio)
    return f"{color}{BLOCK * filled}{TRACK}{BLOCK * (width - filled)}{RESET}"


def _row(label: str, label_width: int, content: str) -> str:
    return f"{WHITE}{label.ljust(label_width)}{RESET}{content}"


def _table_row(cells: list[str], columns: tuple[tuple[str, int, str], ...]) -> str:
    """Alinea títulos y contenido según (título, ancho, alineación), sin contar ANSI."""
    aligned = []
    for cell, (_, width, alignment) in zip(cells, columns):
        width += len(cell) - _visible_len(cell)
        aligned.append(f"{cell:{alignment}{width}}")
    return TABLE_COLUMN_GAP.join(aligned)


def _fill_rows(rows: list[str], height: int) -> list[str]:
    """Completa con filas vacías hasta `height`, para que el panel tenga alto fijo."""
    return rows + [""] * (height - len(rows))


def _build_box(
    title: str, rows: list[str], width: int, subtitle: str = ""
) -> list[str]:
    """Devuelve las líneas de un panel: borde superior, filas y borde inferior.

    `subtitle` se escribe en gris a continuación del título. El alto del panel
    lo determina la cantidad de `rows`."""
    label = f" {title} "
    sub_label = f" {subtitle} " if subtitle else ""
    inner_width = width - 4  # Borde + espacio a cada lado

    top = (
        f"{BORDER}╭─{TITLE_STYLE}{BOLD}{label}{RESET}{GRAY}{sub_label}{RESET}"
        f"{BORDER}{'─' * (width - 3 - len(label) - len(sub_label))}╮{RESET}"
    )
    bottom = f"{BORDER}╰{'─' * (width - 2)}╯{RESET}"

    body = [
        f"{BORDER}│{RESET} {_pad(row, inner_width)} {BORDER}│{RESET}" for row in rows
    ]

    return [top, *body, bottom]


def _print_box(title: str, rows: list[str], subtitle: str = "") -> None:
    """Imprime un panel que ocupa todo el ancho de la interfaz."""
    print("\n".join(_build_box(title, rows, WIDTH, subtitle)))


def _print_side_by_side(
    left: list[str], left_width: int, right: list[str], right_width: int
) -> None:
    """Imprime dos paneles uno al lado del otro.

    Si tienen distinta altura, al más bajo se le completa con espacios en blanco."""
    height = max(len(left), len(right))
    left = left + [" " * left_width] * (height - len(left))
    right = right + [" " * right_width] * (height - len(right))
    for left_line, right_line in zip(left, right):
        print(f"{left_line}{right_line}")


# ---------------------------------------------------------------------------
# Datos derivados del reporte
# ---------------------------------------------------------------------------


def _running(report: Report) -> PCB | None:
    """Proceso en ejecución, o None si la CPU está ociosa."""
    return next(
        (
            pcb
            for pcb in report["process_table"].values()
            if pcb.control.state == ProcessState.RUNNING
        ),
        None,
    )


def _finished_text(report: Report) -> str:
    """Lista los PID terminados, o '— ninguno' si todavía no terminó ningún proceso."""
    labels = [
        _process_label(pid)
        for pid, pcb in sorted(report["process_table"].items())
        if pcb.is_finished
    ]
    return ", ".join(labels) if labels else f"{GRAY}— ninguno{RESET}"


def _find_partition(report: Report, pcb: PCB) -> Partition | None:
    return next(
        (p for p in report["memory"]["partitions"] if p.pid == pcb.identity.pid),
        None,
    )


def _process_color(pid: int) -> int:
    """Color (de 256) fijo para cada proceso, para que no cambie entre pasos."""
    return PROCESS_COLORS[pid % len(PROCESS_COLORS)]


def _process_dim_color(pid: int) -> int:
    """Obtiene el tinte tenue del sombreado sobre el fondo gris oscuro de espera."""
    color = _process_color(pid) - 16
    red, remainder = divmod(color, 36)
    green, blue = divmod(remainder, 6)
    return 16 + 36 * (red // 2) + 6 * (green // 2) + blue // 2


def _process_label(pid: int) -> str:
    color = f"\033[38;5;{_process_color(pid)}m"
    return f"{color}{BOLD}P{pid}{RESET}"


def _next_arrival_text(report: Report) -> str:
    """Texto con el instante y los PID del próximo arribo, o '— ninguno'."""
    next_arrival = report.get("next_arrival")
    if next_arrival is None:
        return f"{GRAY}— ninguno{RESET}"

    time, pids = next_arrival
    labels = ", ".join(f"P{pid}" for pid in pids)
    return f"{WHITE}t={time}{RESET}  {GRAY}({labels}){RESET}"


# ---------------------------------------------------------------------------
# Encabezado: PROCESADOR y RESUMEN
# ---------------------------------------------------------------------------


def _cpu_rows(report: Report) -> list[str]:
    """Cuatro filas con el proceso en CPU, su avance, restante y tiempos de arribo y primer despacho."""
    label_width = 9
    bar_width = 28
    pcb = _running(report)

    if pcb is None:
        return [f"{GRAY}CPU ociosa{RESET}", "", "", ""]

    burst = pcb.spec.burst_time
    remaining = pcb.control.remaining_time
    executed = burst - remaining
    percentage = round(executed / burst * 100) if burst > 0 else 0

    process = (
        f"{BADGE}{BOLD} P{pcb.identity.pid} {RESET} {GRAY}({pcb.spec.size}K){RESET}"
    )

    progress = (
        f"{_bar(executed, burst, bar_width, BLUE)} {WHITE}{BOLD}{percentage}%{RESET}"
    )

    remaining_info = f"{YELLOW}{BOLD}{remaining}u{RESET}"

    arrival_info = f"{WHITE}t={pcb.spec.arrival_time}{RESET}"
    first_dispatch_time = next(
        (
            event.time
            for event in report["events"]
            if event.pid == pcb.identity.pid and event.type == EventTy.Dispatch
        ),
        None,
    )
    if first_dispatch_time is not None:
        arrival_info += f"  {GRAY}1era vez en CPU: t={first_dispatch_time}{RESET}"

    return [
        _row("Proceso", label_width, process),
        _row("Avance", label_width, progress),
        _row("Restante", label_width, remaining_info),
        _row("Arribó", label_width, arrival_info),
    ]


def _summary_rows(report: Report) -> list[str]:
    """Filas del panel RESUMEN (siempre 4)."""
    label_width = 18
    bar_width = 18

    # Un punto por cada cupo de multiprogramación: ocupado (verde) o libre (gris)
    degree = report["scheduler"]["multiprogramming_degree"]
    dots = f"{GREEN}{'●' * degree}{GRAY}{'○' * (MAX_MULTIPROGRAMMING - degree)}{RESET}"
    multiprogramming = f"{dots} {WHITE}{BOLD}{degree}/{MAX_MULTIPROGRAMMING}{RESET}"

    memory = report["memory"]
    used = sum(p.size for p in memory["partitions"])
    size = memory["end"] - memory["start"]
    memory_info = (
        f"{_bar(used, size, bar_width, LAVENDER)} {WHITE}{used}/{size}K{RESET}"
    )

    return [
        _row("Multiprogramación", label_width, multiprogramming),
        _row("Memoria usuario", label_width, memory_info),
        _row("Terminados", label_width, _finished_text(report)),
        _row("Próximo arribo", label_width, _next_arrival_text(report)),
    ]


def _draw_heading(report: Report) -> None:
    """Dibuja los paneles PROCESADOR y RESUMEN uno al lado del otro."""
    cpu_width = WIDTH // 2
    summary_width = WIDTH - cpu_width
    _print_side_by_side(
        _build_box("PROCESADOR", _cpu_rows(report), cpu_width),
        cpu_width,
        _build_box("RESUMEN", _summary_rows(report), summary_width),
        summary_width,
    )


# ---------------------------------------------------------------------------
# Colas
# ---------------------------------------------------------------------------

# Ancho de la columna con el nombre de cada cola (el de "Listo/Susp." más 2)
QUEUE_LABEL_WIDTH = 13

# (título, clave en report["scheduler"]["queues"], color del título)
QUEUES = (
    ("Nuevo", "new", WHITE),
    ("Listo", "ready", YELLOW),
    ("Listo/Susp.", "ready_suspended", ORANGE),
)


def _queue_badge(pcb: PCB) -> str:
    """Etiqueta del proceso con el fondo de su color, igual que en la barra de memoria."""
    color = _process_color(pcb.identity.pid)
    return f"\033[48;5;{color}m{DARK_TEXT}{BOLD} P{pcb.identity.pid} {RESET}"


def _queue_rows(report: Report) -> list[str]:
    """Una fila por cola: título, separador y los badges en el orden de la cola."""
    rows = []
    for title, key, color in QUEUES:
        badges = " ".join(
            _queue_badge(pcb) for pcb in report["scheduler"]["queues"][key]
        )
        rows.append(
            f"{color}{BOLD}{title.ljust(QUEUE_LABEL_WIDTH)}{RESET}"
            f"{GRAY}│{RESET} {badges or f'{GRAY}(vacía){RESET}'}"
        )
    return rows


def _draw_queues(report: Report) -> None:
    """Dibuja el panel COLAS ocupando todo el ancho."""
    _print_box("COLAS", _queue_rows(report))


# ---------------------------------------------------------------------------
# Memoria principal
# ---------------------------------------------------------------------------


def _memory_blocks(report: Report) -> list[Partition | Gap]:
    """Particiones y huecos de la memoria de usuario, ordenados por dirección."""
    memory = report["memory"]
    return sorted([*memory["partitions"], *memory["gaps"]], key=lambda b: b.base)


def _memory_segment(block: Partition | Gap | None, columns: int) -> str:
    """Un tramo de la barra. `block=None` representa al sistema operativo."""
    if block is None:
        style, text = OS_STYLE, "SO"
    elif isinstance(block, Gap):
        style, text = FREE_STYLE, "libre" if columns >= 7 else ""
    else:
        style = f"\033[48;5;{_process_color(block.pid)}m{DARK_TEXT}{BOLD}"
        text = f"P{block.pid}"
    return f"{style}{_center(text, columns)}{RESET}"


def _memory_bar(report: Report, blocks: list[Partition | Gap]) -> list[str]:
    """Barra proporcional de la memoria con su regla de direcciones debajo."""
    # Ancho interno del panel, menos lugar para " (K)" al final de la regla
    width = WIDTH - 4 - 4
    memory = report["memory"]
    # El SO ocupa [0, start) y la memoria de usuario llega hasta `end`
    total = memory["end"]
    segments: list[tuple[int, int, Partition | Gap | None]] = [
        (0, memory["start"], None),
        *((b.base, b.size, b) for b in blocks),
    ]

    bar = ""
    ruler = [" "] * width

    def write_label(address: int, column: int) -> None:
        """Escribe una dirección en la regla si no pisa a otra (deja 1 de margen)."""
        label = str(address)
        end = column + len(label)
        surroundings = ruler[max(column - 1, 0) : end + 1]
        if end <= width and all(char == " " for char in surroundings):
            ruler[column:end] = label

    # El tamaño total se escribe primero, pegado a la derecha, para que siempre se vea
    write_label(total, width - len(str(total)))

    for base, size, block in segments:
        first = round(base / total * width)
        columns = round((base + size) / total * width) - first
        if columns <= 0:
            continue
        bar += _memory_segment(block, columns)
        write_label(base, first)

    return [bar, f"{GRAY}{''.join(ruler)} (K){RESET}"]


# Mínimo de filas de contenido de la tabla de memoria, sin contar el encabezado
MEMORY_MIN_ROWS = 4

# Columnas de la tabla de memoria: (título, ancho, alineación del título y contenido)
MEMORY_COLUMNS = (
    ("Partición", 9, "^"),
    ("Inicio", 6, ">"),
    ("Fin", 6, ">"),
    ("Tamaño", 6, ">"),
    ("Proceso", 7, "^"),
)


def _memory_table(report: Report) -> list[str]:
    """Muestra el SO y las particiones por dirección, con un mínimo de filas de contenido."""
    start = report["memory"]["start"]
    dash = f"{GRAY}—{RESET}"

    headers = [title for title, _, _ in MEMORY_COLUMNS]
    rows = [f"{BOLD}{WHITE}{_table_row(headers, MEMORY_COLUMNS)}{RESET}"]

    rows.append(
        _table_row(
            [
                f"{GRAY}SO{RESET}",
                f"{WHITE}0K{RESET}",
                f"{WHITE}{start}K{RESET}",
                f"{WHITE}{start}K{RESET}",
                dash,
            ],
            MEMORY_COLUMNS,
        )
    )

    partitions = sorted(report["memory"]["partitions"], key=lambda part: part.base)
    for partition in partitions:
        cells = [
            f"{GRAY}#{partition.number}{RESET}",
            f"{WHITE}{partition.base}K{RESET}",
            f"{WHITE}{partition.limit}K{RESET}",
            f"{WHITE}{partition.size}K{RESET}",
            _process_label(partition.pid),
        ]
        rows.append(_table_row(cells, MEMORY_COLUMNS))

    return _fill_rows(rows, MEMORY_MIN_ROWS + 1)


def _memory_footer(report: Report) -> str:
    gaps: list[Gap] = report["memory"]["gaps"]
    free = sum(gap.size for gap in gaps)
    largest = max(gaps, key=lambda gap: gap.size, default=None)
    smallest = min(gaps, key=lambda gap: gap.size, default=None)

    largest_text = f"{largest.size}K" if largest else "—"
    smallest_text = f"{smallest.size}K" if smallest else "—"
    return (
        f"{GRAY}Libre: {WHITE}{free}K{GRAY} en {len(gaps)} hueco(s)"
        f" · mayor: {WHITE}{largest_text}{GRAY} · menor: {WHITE}{smallest_text}{RESET}"
    )


def _draw_memory(report: Report) -> None:
    """Dibuja el panel MEMORIA PRINCIPAL ocupando todo el ancho."""
    blocks = _memory_blocks(report)
    rows = [
        "",
        *_memory_bar(report, blocks),
        "",
        *_memory_table(report),
        "",
        _memory_footer(report),
    ]
    _print_box("MEMORIA PRINCIPAL", rows)


# ---------------------------------------------------------------------------
# Procesos
# ---------------------------------------------------------------------------

# Mínimo de filas del panel PROCESOS y cantidad de filas del panel EVENTOS
PANEL_ROWS = 9

# Columnas de la tabla de procesos: (título, ancho, alineación del título y contenido)
PROCESS_COLUMNS = (
    ("PID", 5, "^"),
    ("Tamaño", 8, ">"),
    ("Arr.", 5, "^"),
    ("Irr.", 5, "^"),
    ("Restante", 9, "^"),
    ("Estado", 14, "<"),
    ("Partición", 10, "^"),
)

# Texto y color con que se muestra cada estado de un proceso
STATE_STYLES = {
    ProcessState.NEW: ("Nuevo", WHITE),
    ProcessState.READY: ("Listo", YELLOW),
    ProcessState.READY_SUSPENDED: ("Listo/Susp.", ORANGE),
    ProcessState.RUNNING: ("Ejecución", GREEN),
    ProcessState.FINISHED: ("Terminado", BLUE),
}


def _process_box_width() -> int:
    """Ancho mínimo del panel PROCESOS: columnas, separaciones y bordes."""
    columns_width = sum(width for _, width, _ in PROCESS_COLUMNS)
    gaps_width = len(TABLE_COLUMN_GAP) * (len(PROCESS_COLUMNS) - 1)
    return columns_width + gaps_width + 4


def _process_rows(report: Report) -> list[str]:
    """Una fila por proceso arribado, con círculo y descripción del estado y partición."""
    headers = [title for title, _, _ in PROCESS_COLUMNS]
    rows = [f"{BOLD}{GRAY}{_table_row(headers, PROCESS_COLUMNS)}{RESET}"]

    process_table = report["process_table"]
    if not process_table:
        rows.append(f"{GRAY}— ningún proceso arribó todavía{RESET}")

    for pid, pcb in sorted(process_table.items()):
        spec = pcb.spec
        state, color = STATE_STYLES[pcb.control.state]
        remaining = pcb.control.remaining_time
        partition = _find_partition(report, pcb)

        partition_number = (
            f"{WHITE}#{partition.number}{RESET}"
            if partition is not None
            else f"{GRAY}—{RESET}"
        )
        cells = [
            _process_label(pid),
            f"{WHITE}{spec.size}K{RESET}",
            f"{WHITE}{spec.arrival_time}{RESET}",
            f"{WHITE}{spec.burst_time}{RESET}",
            f"{WHITE}{remaining}u{RESET}",
            f"{color}● {state}{RESET}",
            partition_number,
        ]
        rows.append(_table_row(cells, PROCESS_COLUMNS))

    return _fill_rows(rows, PANEL_ROWS)


# ---------------------------------------------------------------------------
# Eventos
# ---------------------------------------------------------------------------

# Color del estado de destino de cada evento reciente; los viejos se muestran en gris
EVENT_COLORS = {
    EventTy.Arrival: STATE_STYLES[ProcessState.NEW][1],
    EventTy.Admission: STATE_STYLES[ProcessState.READY][1],
    EventTy.Suspension: STATE_STYLES[ProcessState.READY_SUSPENDED][1],
    EventTy.Activation: STATE_STYLES[ProcessState.READY][1],
    EventTy.Dispatch: STATE_STYLES[ProcessState.RUNNING][1],
    EventTy.Finalization: STATE_STYLES[ProcessState.FINISHED][1],
}


def _is_recent(report: Report, event: Event) -> bool:
    """Indica si el evento ocurrió en el último paso (se resalta en pantalla)."""
    # step() registra los eventos y recién después avanza el reloj, por eso
    # los del último paso quedan con tiempo `time - 1`.
    return event.time == report["time"] - 1


def _event_rows(report: Report, width: int) -> list[str]:
    """Muestra los últimos eventos completos, continuando en otra línea si hace falta."""
    events = report["events"][-PANEL_ROWS:]

    rows = []
    for event in reversed(events):
        recent = _is_recent(report, event)
        color = EVENT_COLORS[event.type] if recent else GRAY
        marker = f"{YELLOW}▸{RESET}" if recent else " "
        time = f"t={event.time:<3}"
        prefix_width = 1 + len(time)
        text_width = width - 4 - prefix_width
        lines = wrap(f"P{event.pid} {event.message}", width=text_width)
        for index, line in enumerate(lines):
            prefix = (
                f"{marker}{GRAY}{time}{RESET}" if index == 0 else " " * prefix_width
            )
            rows.append(f"{prefix}{color}{line}{RESET}")

    if not rows:
        rows.append(f"{GRAY}(sin eventos todavía){RESET}")
    return _fill_rows(rows, PANEL_ROWS)


# ---------------------------------------------------------------------------
# Procesos y eventos, lado a lado
# ---------------------------------------------------------------------------


def _draw_processes_and_events(report: Report) -> None:
    """Dibuja los paneles PROCESOS y EVENTOS uno al lado del otro.

    Reparte el ancho en 2/3 y 1/3, dando más espacio a EVENTOS si lo necesita."""
    process_rows = _process_rows(report)
    minimum_process_width = max(
        _process_box_width(), max(_visible_len(row) for row in process_rows) + 4
    )
    event_rows = _event_rows(report, WIDTH)
    required_event_width = max(_visible_len(row) for row in event_rows) + 4
    event_width = min(
        max(WIDTH // 3, required_event_width), WIDTH - minimum_process_width
    )
    process_width = WIDTH - event_width
    _print_side_by_side(
        _build_box("PROCESOS", process_rows, process_width),
        process_width,
        _build_box("EVENTOS", _event_rows(report, event_width), event_width),
        event_width,
    )


# ---------------------------------------------------------------------------
# Resumen final
# ---------------------------------------------------------------------------

# Columnas del resumen: (título, ancho, alineación del título y contenido)
FINAL_PROCESS_COLUMNS = (
    ("PID", 10, "<"),
    ("Tamaño", 8, ">"),
    ("Arribo", 8, "^"),
    ("Irrupción", 10, "^"),
    ("1ª CPU", 9, "^"),
    ("Fin", 8, "^"),
    ("Retorno", 9, "^"),
    ("Espera", 9, "^"),
)


def _final_process_rows(report: Report) -> list[str]:
    """Lista los tiempos de cada PCB y los promedios de retorno y espera."""
    first_dispatch_times: dict[int, int] = {}
    for event in report["events"]:
        if event.type == EventTy.Dispatch:
            first_dispatch_times.setdefault(event.pid, event.time)

    headers = [title for title, _, _ in FINAL_PROCESS_COLUMNS]
    rows = [f"{BOLD}{GRAY}{_table_row(headers, FINAL_PROCESS_COLUMNS)}{RESET}"]
    table_width = _visible_len(rows[0])
    separator = f"{GRAY}{'─' * table_width}{RESET}"
    rows.append(separator)

    processes = sorted(report["process_table"].items())
    if not processes:
        rows.append(f"{GRAY}— ningún proceso cargado{RESET}")

    turnaround_times = []
    waiting_times = []
    for pid, pcb in processes:
        spec = pcb.spec
        first_dispatch = first_dispatch_times.get(pid)
        finish = pcb.metrics.finish_time
        turnaround = pcb.turnaround_time
        waiting = pcb.waiting_time
        cells = [
            _process_label(pid),
            f"{WHITE}{spec.size}K{RESET}",
            f"{WHITE}{spec.arrival_time}{RESET}",
            f"{WHITE}{spec.burst_time}{RESET}",
            f"{WHITE}{first_dispatch if first_dispatch is not None else '—'}{RESET}",
            f"{WHITE}{finish if finish is not None else '—'}{RESET}",
            f"{GREEN}{turnaround if turnaround is not None else '—'}{RESET}",
            f"{YELLOW}{waiting if waiting is not None else '—'}{RESET}",
        ]
        rows.append(_table_row(cells, FINAL_PROCESS_COLUMNS))
        if turnaround is not None:
            turnaround_times.append(turnaround)
        if waiting is not None:
            waiting_times.append(waiting)

    average_turnaround = (
        f"{sum(turnaround_times) / len(turnaround_times):.2f}"
        if turnaround_times
        else "—"
    )
    average_waiting = (
        f"{sum(waiting_times) / len(waiting_times):.2f}" if waiting_times else "—"
    )
    averages = [
        f"{WHITE}{BOLD}Promedios{RESET}",
        "",
        "",
        "",
        "",
        "",
        f"{GREEN}{BOLD}{average_turnaround}{RESET}",
        f"{YELLOW}{BOLD}{average_waiting}{RESET}",
    ]
    return [*rows, separator, _table_row(averages, FINAL_PROCESS_COLUMNS)]


def _final_system_rows(report: Report) -> list[str]:
    """Muestra duración, trabajos terminados y rendimiento con su intervalo promedio."""
    processes = list(report["process_table"].values())
    total_time = report["time"]
    finished = sum(pcb.is_finished for pcb in processes)
    throughput = finished / total_time if total_time > 0 else 0
    interval_info = (
        f"  {GRAY}(≈ 1 proceso cada {total_time / finished:.2f} unidades){RESET}"
        if finished > 0 and total_time > 0
        else ""
    )
    label_width = 30

    return [
        _row(
            "Tiempo total de simulación",
            label_width,
            f"{WHITE}{BOLD}{total_time} u{RESET}",
        ),
        _row("Procesos terminados", label_width, f"{WHITE}{BOLD}{finished}{RESET}"),
        _row(
            "Rendimiento",
            label_width,
            f"{GREEN}{BOLD}{throughput:.4f} procesos/u{RESET}{interval_info}",
        ),
    ]


# ---------------------------------------------------------------------------
# Línea de vida de los procesos
# ---------------------------------------------------------------------------

LifetimeInterval = tuple[int, int, ProcessState]

LIFETIME_WAIT_BACKGROUND = 234

LIFETIME_EVENT_STATES = {
    EventTy.Arrival: ProcessState.NEW,
    EventTy.Admission: ProcessState.READY,
    EventTy.Suspension: ProcessState.READY_SUSPENDED,
    EventTy.Activation: ProcessState.READY,
    EventTy.Dispatch: ProcessState.RUNNING,
    EventTy.Finalization: ProcessState.FINISHED,
}


def _lifetime_intervals(report: Report) -> dict[int, list[LifetimeInterval]]:
    """Reconstruye intervalos [inicio, fin), deduciendo desalojos de cada despacho."""
    intervals: dict[int, list[LifetimeInterval]] = {
        pid: [] for pid in report["process_table"]
    }
    states: dict[int, tuple[int, ProcessState]] = {}
    running: int | None = None

    for event in report["events"]:
        transitions: list[tuple[int, ProcessState]] = []
        if event.type == EventTy.Dispatch:
            if running is not None:
                transitions.append((running, ProcessState.READY))
            running = event.pid
        elif event.type == EventTy.Finalization and running == event.pid:
            running = None

        transitions.append((event.pid, LIFETIME_EVENT_STATES[event.type]))
        for pid, state in transitions:
            previous = states.get(pid)
            if previous is not None:
                start, previous_state = previous
                if start < event.time and previous_state != ProcessState.FINISHED:
                    intervals[pid].append((start, event.time, previous_state))
            states[pid] = (event.time, state)

    for pid, (start, state) in states.items():
        if start < report["time"] and state != ProcessState.FINISHED:
            intervals[pid].append((start, report["time"], state))
    return intervals


def _lifetime_rows(report: Report) -> list[str]:
    """Dibuja cada ventana con una fila por PID y su escala temporal al pie."""
    if not report["process_table"]:
        return [f"{GRAY}— ningún proceso cargado{RESET}"]

    intervals = _lifetime_intervals(report)
    total_time = report["time"]
    pid_width = max(3, max(len(f"P{pid}") for pid in intervals))
    prefix_width = pid_width + 3
    window_size = WIDTH - 4 - prefix_width - len(str(total_time))
    execution_sample = _lifetime_line(0, [(0, 2, ProcessState.RUNNING)], 0, 2)
    waiting_sample = _lifetime_line(0, [(0, 2, ProcessState.READY)], 0, 2)
    rows = ["", f"Referencias: {execution_sample} Ejecución  {waiting_sample} Espera"]

    for start in range(0, max(total_time, 1), window_size):
        end = min(start + window_size, total_time)
        rows.append("")
        for pid, spans in sorted(intervals.items()):
            label = _pad(_process_label(pid), pid_width)
            line = _lifetime_line(pid, spans, start, end)
            rows.append(f"{label} {GRAY}│{RESET} {line}")
        time_label = _pad(f"{GRAY}t{RESET}", pid_width)
        ruler = _lifetime_ruler(start, end)
        rows.append(f"{time_label} {GRAY}│ {ruler}{RESET}")
    return rows


def _lifetime_ruler(start: int, end: int) -> str:
    """Marca los extremos y múltiplos de cinco sin superponer etiquetas."""
    ruler = [" "] * (end - start + len(str(end)))
    first_tick = (start // 5 + 1) * 5
    for time in [end, start, *range(first_tick, end, 5)]:
        column = time - start
        label = str(time)
        surroundings = ruler[max(0, column - 1) : column + len(label) + 1]
        if all(char == " " for char in surroundings):
            ruler[column : column + len(label)] = label
    return "".join(ruler)


def _lifetime_line(
    pid: int, intervals: list[LifetimeInterval], start: int, end: int
) -> str:
    """Dibuja CPU en color brillante y espera gris oscura con un sombreado del tinte del PID."""
    segments = []
    cursor = start
    for interval_start, interval_end, state in intervals:
        left = max(start, interval_start)
        right = min(end, interval_end)
        if left >= right:
            continue
        segments.append(" " * (left - cursor))
        if state == ProcessState.RUNNING:
            color = _process_color(pid)
            text = " " * (right - left)
            segment = f"\033[48;5;{color}m{text}{RESET}"
        else:
            color = _process_dim_color(pid)
            text = "░" * (right - left)
            segment = (
                f"\033[48;5;{LIFETIME_WAIT_BACKGROUND}m\033[38;5;{color}m{text}{RESET}"
            )
        segments.append(segment)
        cursor = right
    segments.append(" " * (end - cursor))
    return "".join(segments)
