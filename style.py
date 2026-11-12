import re

WIDTH = 100

PADDING = "  "

# Secuencias ANSI. https://handwiki.org/wiki/ANSI_escape_code
# \033[ - Inicia una secuencia y ; separa parámetros
CLEAR = "\033[3J\033[2J\033[H"
RESET = "\033[0m"
BOLD = "\033[1m"
BORDER = "\033[38;5;67m"
TITLE_STYLE = "\033[38;5;117m"
GRAY = "\033[38;5;244m"
GREEN = "\033[38;5;114m"
YELLOW = "\033[38;5;221m"
BLUE = "\033[38;5;75m"
ORANGE = "\033[38;5;209m"
WHITE = "\033[38;5;252m"
LAVENDER = "\033[38;5;147m"
TRACK = "\033[38;5;237m"  # Fondo de las barras de progreso vacías
BADGE = "\033[48;5;221m\033[38;5;16m"  # Texto oscuro sobre fondo amarillo

# Estilos de la barra de memoria (fondo + color del texto)
DARK_TEXT = "\033[38;5;16m"  # Texto oscuro para escribir sobre fondos de color
OS_STYLE = f"\033[48;5;240m\033[38;5;252m{BOLD}"  # Segmento del sistema operativo
FREE_STYLE = "\033[48;5;236m\033[38;5;244m"  # Segmento de memoria libre

# Colores (de 256) para distinguir a cada proceso en la memoria
PROCESS_COLORS = (80, 221, 177, 114, 209, 75, 147, 203)

ANSI_PATTERN = re.compile(r"\033\[[0-9;]*m")
BLOCK = "█"
