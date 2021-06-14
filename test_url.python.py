from scraper.scraper import get_default_fetch_map, get_center_platform, fix_scrap_urls

url = input("merci d'entrer une url")

fetch_map = get_default_fetch_map()

rdv_site_web = fix_scrap_urls(url)
platform = get_center_platform(url, fetch_map=fetch_map)

print("platform is")
