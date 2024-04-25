import logging
from logging.handlers import RotatingFileHandler

logger = logging.getLogger()
logger.setLevel(logging.INFO)

console_log = logging.StreamHandler()
console_log.setLevel(logging.INFO)

file_log = RotatingFileHandler(filename="access.log")
file_log.setLevel(logging.INFO)

formatter_console = logging.Formatter(
    "%(asctime)s - %(filename)s "
    "- %(funcName)s- %(lineno)d- "
    "-%(levelname)s - %(message)s"
)
formatter_file = logging.Formatter(
    "%(asctime)s - %(filename)s "
    "- %(funcName)s- %(lineno)d- "
    "-%(levelname)s - %(message)s"
)

console_log.setFormatter(formatter_console)
file_log.setFormatter(formatter_file)

logger.addHandler(console_log)
logger.addHandler(file_log)
