import re
from unidecode import unidecode 

def urlify(s):
    s = re.sub(r"[^\w\s\-]", '', s)
    s = re.sub(r"\s+", '-', s).lower()
    return unidecode(s)
    
