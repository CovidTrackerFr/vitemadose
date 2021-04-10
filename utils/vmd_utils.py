import re

def urlify(s):
    s = re.sub(r"[^\w\s\-]", '', s).lower()
    s = re.sub(r"\s+", '-', s).lower()
    return s
