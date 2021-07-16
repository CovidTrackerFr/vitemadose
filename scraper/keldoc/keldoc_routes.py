from utils.vmd_config import get_conf_platform

KELDOC_CONF = get_conf_platform("keldoc")
KELDOC_API = KELDOC_CONF.get("api")

# Center info route
API_KELDOC_CENTER = KELDOC_API.get("booking")

# Motive list route
API_KELDOC_MOTIVES = KELDOC_API.get("motives")

# Cabinet list route
API_KELDOC_CABINETS = KELDOC_API.get("cabinets")

# Calendar details route
API_KELDOC_CALENDAR = KELDOC_API.get("slots")

API_SPECIALITY_IDS = KELDOC_CONF.get("filters").get("vaccination_speciality_ids")
