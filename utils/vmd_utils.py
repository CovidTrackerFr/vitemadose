import re
import unicodedata
import simplejson as jsoncode
from unidecode import unidecode 

def urlify(s):
    s = re.sub(r"[^\w\s\-]", '', s)
    s = re.sub(r"\s+", '-', s).lower()
    return ''.join(c for c in unidecode(unicodedata.normalize('NFD', s)) if unicodedata.category(c) != 'Mn')
    
