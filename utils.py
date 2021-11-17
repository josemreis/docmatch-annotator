import subprocess
import re
import math
import os
import time

def make_substrings(s, L):
    """splits `s` into substrings of length L"""
    i = 0
    pieces = []
    while i < len(s):
        pieces.append(s[i : i + L])
        i += L
    return pieces


def detect_gedit_width(timeout = 20) -> int:
    """detect the default window width from gedit using wmctrl"""
    # open gedit
    process = subprocess.Popen(["gedit", "just checking the window size..."])
    t = 0
    while not list(os.popen("wmctrl -lGp | grep 'just checking the window size...' > /dev/null/")):
        time.sleep(1)
        t+=1
        if t > timeout:
            raise OSError("Could not open the Gedit window")
    # subset the relevant active window using the pid of the process
    relevant_window = [
        l
        for l in os.popen(f"wmctrl -lpG", "r").read().split("\n")
        if str(process.pid) in l
    ][0]
    # fetch the width
    width = [int(_) for _ in relevant_window.split() if re.match("[0-9]{2,}", _)][2]
    # terminate the process
    process.terminate()
    return width


def write_side_by_side(
    text1,
    text2,
    gedit_width: int,
    header: str = "my_header",
    output_file: str = "/home/jr/Desktop/t.txt",
    print_line_numbers=False,
    col_padding=2,
    delimiter="",
):
    """Concatenate two texts side by side. Only minor changes to: https://github.com/jxmorris12/side-by-side/blob/master/side_by_side/diff.py"""
    if len(delimiter) > col_padding:
        raise ValueError("Delimiter cannot be longer than padding")
    # Split files into lines
    lines1 = text1.split("\n")
    lines2 = text2.split("\n")
    # Get number of digits in line numbers
    max_num_lines = max(len(lines1), len(lines2))
    if print_line_numbers:
        max_num_digits_in_line_num = math.ceil(math.log(max_num_lines))
        col_width = (gedit_width - (max_num_digits_in_line_num) - col_padding) // 2
        line_fmt = "{:<" + str(max_num_digits_in_line_num) + "}"
    else:
        col_width = (gedit_width - col_padding) // 2
        max_num_digits_in_line_num = False
        line_fmt = ""
    # Print lines side by side
    line_fmt += (
        "{:<"
        + str(col_width)
        + "}"
        + (" " * math.floor((col_padding - len(delimiter)) / 2.0))
        + delimiter
        + (" " * math.ceil((col_padding - len(delimiter)) / 2.0))
        + "{:<"
        + str(col_width)
        + "}"
    )

    with open(output_file, "w+") as f:
        print(header, file=f)
        for i in range(max_num_lines):
            # Get rows for this line for file 1.
            l1 = ""
            if i < len(lines1):
                l1 = lines1[i]
            rows1 = make_substrings(l1, col_width)
            # Get rows for this line for file 2.
            l2 = ""
            if i < len(lines2):
                l2 = lines2[i]
            rows2 = make_substrings(l2, col_width)
            # Print rows.
            max_num_rows = max(len(rows1), len(rows2))
            j = 0
            while j < max_num_rows:
                token1 = rows1[j] if j < len(rows1) else ""
                token2 = rows2[j] if j < len(rows2) else ""
                if print_line_numbers:
                    row_num = i if j == 0 else ""
                    print(line_fmt.format(row_num, token1, token2), file=f)
                else:
                    print(line_fmt.format(token1, token2), file=f)
                j += 1
