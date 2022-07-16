import sys
from typing import Literal
from rich import print
from itertools import count

log_styles = {"info": "magenta", "done": "green", "error": "bold red"}

# we can indent based on function nesting.
# subtract this number to handle overhead of all functions
depth_offset = 9


def log(message: str, type: Literal["info", "done", "error"], newline=True):
    """
    A wrapper around rich.print() that gives us centralised control.

    Colour is based on `type`. See the type annotation for options.

    Set newline to False to print the next thing on the same line.
    """
    # show function call nesting. disabled as it's a bit confusing without function names
    # indent = "    " * max(stack_size() - depth_offset, 0)

    # style based on the log message type
    style = log_styles[type]

    end = "\n" if newline is True else ""

    # formatted_message = f"{indent}[{style}]{message}[/]"
    formatted_message = f"[{style}]{message}[/]"

    print(formatted_message, end=end)


def stack_size(size=2):
    """
    Get stack size for caller's frame, i.e. how many functions deep we are.
    Used to nest log messages from inner calls.
    https://stackoverflow.com/a/47956089
    """
    frame = sys._getframe(size)

    for size in count(size):
        frame = frame.f_back
        if not frame:
            return size
    # fallback
    return depth_offset
