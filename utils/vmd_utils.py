import re
import unicodedata
import simplejson as jsoncode

def urlify(s):
    s = re.sub(r"[^\w\s\-]", '', s)
    s = re.sub(r"\s+", '-', s).lower()
    return jsoncode.dumps(unicodedata.normalize('NFKD', s).encode('ASCII', 'ignore')).strip('"')
    
