import csv
import datetime as dt
import io
import json
import os
from multiprocessing import Pool

import pytz
import requests

from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException

import random


from utils.vmd_logger import init_logger
from .departements import to_departement_number, import_departements
from .doctolib.doctolib import fetch_slots as doctolib_fetch_slots
from .keldoc.keldoc import fetch_slots as keldoc_fetch_slots
from .maiia import fetch_slots as maiia_fetch_slots
from .ordoclic import centre_iterator as ordoclic_centre_iterator
from .ordoclic import fetch_slots as ordoclic_fetch_slots

POOL_SIZE = int(os.getenv('POOL_SIZE', 20))
logger = init_logger()


def main():
    with Pool(POOL_SIZE) as pool:
        centres_cherchés = pool.imap_unordered(
            cherche_prochain_rdv_dans_centre,
            centre_iterator(),
            1
        )
        compte_centres, compte_centres_avec_dispo = export_data(centres_cherchés)
        logger.info(f"{compte_centres_avec_dispo} centres de vaccination avaient des disponibilités sur {compte_centres} scannés")
        if compte_centres_avec_dispo == 0:
            logger.error("Aucune disponibilité n'a été trouvée sur aucun centre, c'est bizarre, alors c'est probablement une erreur")
            exit(code=1)


def cherche_prochain_rdv_dans_centre(centre):
    start_date = dt.datetime.now().isoformat()[:10]
    try:
        plateforme, next_slot = fetch_centre_slots(centre['rdv_site_web'], start_date)
    except Exception as e:
        logger.error(f"erreur lors du traitement de la ligne avec le gid {centre['gid']}")
        print(e)
        next_slot = None
        plateforme = None
        

    try:
        departement = to_departement_number(insee_code=centre['com_insee'])
    except ValueError:
        logger.error(f"erreur lors du traitement de la ligne avec le gid {centre['gid']}, com_insee={centre['com_insee']}")
        departement = ''

    logger.info(f'{centre.get("gid", "")!s:>8} {plateforme!s:16} {next_slot or ""!s:32} {departement!s:6}')

    if plateforme == 'Doctolib' and not centre['rdv_site_web'].islower():
        logger.info(f"Centre {centre['rdv_site_web']} URL contained an uppercase - lowering the URL")
        centre['rdv_site_web'] = centre['rdv_site_web'].lower()

    return {
        'departement': departement,
        'nom': centre['nom'],
        'url': centre['rdv_site_web'],
        'plateforme': plateforme,
        'prochain_rdv': next_slot
    }


def sort_center(center):
    if not center:
        return '-'
    if not 'prochain_rdv' in center or not center['prochain_rdv']:
        return '-'
    return center['prochain_rdv']


def export_data(centres_cherchés, outpath_format='data/output/{}.json'):
    compte_centres = 0
    compte_centres_avec_dispo = 0
    par_departement = {
        code: {
            'version': 1,
            'last_updated': dt.datetime.now(tz=pytz.timezone('Europe/Paris')).isoformat(),
            'centres_disponibles': [],
            'centres_indisponibles': []
        }
        for code in import_departements()
    }
    
    for centre in centres_cherchés:
        centre['nom'] = centre['nom'].strip()
        compte_centres += 1

        code_departement = centre['departement']
        
        if code_departement in par_departement:
            if centre['prochain_rdv'] is None:
                par_departement[code_departement]['centres_indisponibles'].append(centre)
            else:
                compte_centres_avec_dispo += 1
                par_departement[code_departement]['centres_disponibles'].append(centre)
        else:
            logger.warning(f"le centre {centre['nom']} ({code_departement}) n'a pas pu être rattaché à un département connu")

    outpath = outpath_format.format("info_centres")
    with open(outpath, "w") as info_centres:
        json.dump(par_departement, info_centres, indent=2)

    for code_departement, disponibilités in par_departement.items():
        if 'centres_disponibles' in disponibilités:
            disponibilités['centres_disponibles'] = sorted(disponibilités['centres_disponibles'], key=sort_center)
        outpath = outpath_format.format(code_departement)
        logger.debug(f'writing result to {outpath} file')
        with open(outpath, "w") as outfile:
            outfile.write(json.dumps(disponibilités, indent=2))

    return compte_centres, compte_centres_avec_dispo


def fetch_centre_slots(rdv_site_web, start_date, fetch_map: dict = None):
    if fetch_map is None:
        # Map platform to implementation.
        # May be overridden for unit testing purposes.
        fetch_map = {
            'Doctolib': doctolib_fetch_slots,
            'Keldoc': keldoc_fetch_slots,
            'Maiia': maiia_fetch_slots,
            'Ordoclic': ordoclic_fetch_slots,
        }

    rdv_site_web = rdv_site_web.strip()

    # Determine platform based on visit URL.
    if rdv_site_web.startswith('https://partners.doctolib.fr') or rdv_site_web.startswith('https://www.doctolib.fr'):
        platform = 'Doctolib'
    elif rdv_site_web.startswith('https://vaccination-covid.keldoc.com'):
        platform = 'Keldoc'
    elif rdv_site_web.startswith('https://www.maiia.com'):
        platform = 'Maiia'
    elif rdv_site_web.startswith('https://app.ordoclic.fr/'):
        platform = 'Ordoclic'
    else:
        return 'Autre', None

    # Dispatch to appropriate implementation.
    fetch_impl = fetch_map[platform]
    return platform, fetch_impl(rdv_site_web, start_date)


def centre_iterator():


    # variable éventuelle pour utiliser le fichier des rendez vous pros
    statut_pro="_paspros"

    # 2 arrays qui vont contenir les données issues des deux fichiers
    centres_scrapés_doctolib={}
    centres_gouvernement_parsed=[]

    # url des deux fichiers
    url_csv_centres_scrapés_doctolib = "./data/input/centres_doctolib_scrape"+statut_pro+".csv"

    url_csv_centres_scrapés_doctolib_gouv = "https://www.data.gouv.fr/fr/datasets/r/5cb21a85-b0b0-4a65-a249-806a040ec372"

    # on récupère les données du csv data.gouv depuis l'url
    response = requests.get(url_csv_centres_scrapés_doctolib_gouv)
    response.raise_for_status()

    # décodage utf-8
    read_csv_gouv = io.StringIO(response.content.decode('utf8'))
    read_csv_gouv= csv.DictReader(read_csv_gouv, delimiter=';')

    # on commence par s'occuper des lignes dans le csv de data gouv 
    for row in read_csv_gouv:
        yield row
                
    for centre in ordoclic_centre_iterator():
        yield centre      
                
    logger.info(f"on passe aux centres scrapés depuis doctolib qui n'existent pas dans le fichier data.gouv")

    # on fait un try/catch pour ne pas tout planter si le fichier csv scrapé n'existe pas
    try:
    
        # on ouvre le fichier csv local des centres scrapés doctolib
        with open(url_csv_centres_scrapés_doctolib, newline='',encoding="utf-8") as url_csv_centres_scrapés_doctolib:

            # on ouvre le dictionnaire avec le bon délimiteur
            read_csv_scrapé = csv.DictReader(url_csv_centres_scrapés_doctolib, delimiter=';')
            
            # on boucle dans le csv data gouv
            for row_scrapée_gouv in read_csv_gouv:
                
                # on récupère une partie tronquée de l'url qui est comparable
                if len(row_scrapée_gouv['rdv_site_web'].split("/"))==6:
                    url_tronquée_gouv=row_scrapée_gouv['rdv_site_web'].split("/")[4]+"/"+row_scrapée_gouv['rdv_site_web'].split("/")[5]
                    
                    # si l'url contient des paramètres get, on les vire.
                    if len(url_tronquée_gouv.split("?"))!=0:
                        url_tronquée_gouv=url_tronquée_gouv.split("?")[0]
                        
                        # on stocke dans l'array les url tronquées du fichier data gouv pour comparer les rendez vous parsés avec celles ci
                        centres_gouvernement_parsed.append(url_tronquée_gouv)

            # on boucle maintenant dans le CSV scrapé depuis doctolib
            for row_scrapée in read_csv_scrapé:
                
                # on récupère la partie tronquée de l'url scrapée pour comparer
                if len(row_scrapée['rdv_site_web'].split("/"))==6:
                    url_tronquée=row_scrapée['rdv_site_web'].split("/")[4]+"/"+row_scrapée['rdv_site_web'].split("/")[5]

                    # si l'url contient des paramètres get, on les vire
                    if len(url_tronquée.split("?"))!=0:
                        url_tronquée=url_tronquée.split("?")[0]

                        # pour les centres scrapés depuis le csv local, on créé une array associative avec l'url en value et l'url tronquée à comparer en clé
                        centres_scrapés_doctolib[url_tronquée]=row_scrapée['rdv_site_web']
                        
                
                # On compte le nombre de fois où l'url parsée est dans le fichier du gouvernement.
                if centres_gouvernement_parsed.count(url_tronquée)==0:
                
                    # On génère une ligne de dictionnaire sur le format d'une ligne du fichier data gouv lue par un dictionnaire csv
                    artificial_dict={'gid': row_scrapée["gid"], 'nom':row_scrapée["nom"], 'com_insee':row_scrapée["com_insee"], 'rdv_site_web':row_scrapée["rdv_site_web"]}
                    yield artificial_dict
                        
    except EnvironmentError: 
        logger.info(f"erreur lors de la récup du csv de scrape, pensez à vérifier qu'il existe")

    
# Scrape de doctolib, téléchargement des centres en csv
def doctolib_getcsv_scrap(is_professionnel):

    # J'ai réencodé une array avec tous les départements sans accents etc.. associés à leur numéro
    departements={"01":"ain","02":"aisne","03":"allier","04":"alpes-de-haute-provence","05":"hautes-alpes","09":"alpes-maritimes","07":"ardeche","08":"ardennes","09":"ariege","10":"aube","11":"aude","12":"aveyron","13":"bouches-du-rhone","14":"calvados","15":"cantal","16":"charente","17":"charente-maritime","18":"cher","19":"correze","2A":"corse-du-sud","2B":"haute-corse","21":"cote-d-or","22":"cotes-d-armor","23":"creuse","24":"dordogne","25":"doubs","26":"drome","27":"eure","28":"eure-et-loir","29":"finistere","30":"gard","31":"haute-garonne","32":"gers","33":"gironde","34":"herault","35":"ille-et-vilaine","36":"indre","37":"indre-et-loire","38":"isere","39":"jura","40":"landes","41":"loir-et-cher","42":"loire","43":"haute-loire","44":"loire-atlantique","45":"loiret","46":"lot","47":"lot-et-garonne","48":"lozere","49":"maine-et-loire","50":"manche","51":"marne","52":"haute-marne","53":"mayenne","54":"meurthe-et-moselle","55":"meuse","56":"morbihan","57":"moselle","58":"nievre","59":"nord","60":"oise","61":"orne","62":"pas-de-calais","63":"puy-de-dome","64":"pyrenees-atlantiques","65":"hautes-pyrenees","66":"pyrenees-orientales","67":"bas-rhin","68":"haut-rhin","69":"rhone","70":"haute-saone","71":"saone-et-loire","72":"sarthe","73":"savoie","74":"haute-savoie","75":"paris","76":"seine-maritime","77":"seine-et-marne","78":"yvelines","79":"deux-sevres","80":"somme","81":"tarn","82":"tarn-et-garonne","83":"var","84":"vaucluse","85":"vendee","86":"vienne","87":"haute-vienne","88":"vosges","89":"yonne","90":"territoire-de-belfort","91":"essonne","92":"hauts-de-seine","93":"seine-saint-denis","94":"val-de-marne","95":"val-d-oise","971":"guadeloupe","972":"martinique","973":"guyane","974":"la-reunion","975":"mayotte"}

                # Pour les pas pros

    # On créée le fichier et on met les en tête des colonnes. Encodage utf8 pour les accents
    with open('./data/input/centres_doctolib_scrape_paspros.csv', mode='w',encoding='utf-8') as fichier_csv:
        ecriture_csv = csv.writer(fichier_csv, delimiter=';', lineterminator='\n', quoting=csv.QUOTE_MINIMAL)
        ecriture_csv.writerow(["gid","nom","com_insee","rdv_site_web"])

                # Pour les pros

        # On créée le fichier et on met les en tête des colonnes. Encodage utf8 pour les accents
        with open('./data/input/centres_doctolib_scrape_pros.csv', mode='w',encoding='utf-8') as fichier_csv:
            ecriture_csv = csv.writer(fichier_csv, delimiter=';', lineterminator='\n', quoting=csv.QUOTE_MINIMAL)
            ecriture_csv.writerow(["gid","nom","com_insee","rdv_site_web"])

            for numero_departement in departements:

                # On récupère le nom du département à partir du numéro grace à l'array associative
                nom_departement=departements[numero_departement]

                # Options du webdriver
                options = Options()
                options.headless = True
                options.binary_location = r'C:\Program Files\Mozilla Firefox\firefox.exe'
                driver = webdriver.Firefox(
                    executable_path=r'C:\Users\AppData\Local\Programs\Python\Python38-32\geckodriver.exe', firefox_options=options)


                # On prépare l'adaptation de l'url selon que pro de santé ou non.
                if is_professionnel==True:
                    type_patient="vaccination-covid-19-pour-les-professionnels-medico-sociaux"
                    csv_varname="_pros"
                    
                else:
                    type_patient="vaccination-covid-19"
                    csv_varname="_paspros"


                # On récupère les rdvs du répartement via le nom du département
                url = "https://www.doctolib.fr/"+type_patient+"/"+nom_departement+"?ref_visit_motive_ids[]=6970&ref_visit_motive_ids[]=7005&ref_visit_motive_ids[]=7107"
                driver.get(url)



                # Array intermédiaire qui va contenir la liste des centres récupérés
                array_centres_dep = {}

                # Boucle infinie (j'ai pas trouvé mieux)

                remain_pages = True

                while remain_pages == True: 

                    # On récupère les centres pour lesquels il n'y a pas écrit "dans les environs de" avant
                    liste_centres_dep = driver.find_elements_by_xpath(
                        "//div[contains(@class,'search-results-col-list')]/div/following-sibling::div[not(preceding::*[contains(text(),'dans les environs de')])]/div/div/div/h3/a")

                    # Pour chaque centre, on récupère l'url et le nom et on les ajoute dans l'array associative
                    for centre in liste_centres_dep:
                        if centre.get_attribute('href'):
                            array_centres_dep[centre.text]=centre.get_attribute('href')

                    # Si aucun centre "vraiment" dans le département (pas dans les environs de)
                    if not liste_centres_dep:

                        # On est sorti des centres du département, on break
                        remain_pages=False
                        break

                    # On cherche si il existe un bouton "suivant" donc d'autres pages
                    try:
                        driver.find_element_by_xpath("//div[@class='next']/*")

                    # Si il n'y a pas de bouton suivant
                    except NoSuchElementException:

                        # C'est la dernière page, on break
                        remain_pages=alse
                        break

                    else:
                        # Il y a un bouton suivant, on clique puis on boucle
                        driver.find_element_by_xpath("//div[@class='next']").click()

                # On kille le driver
                driver.quit()

                # Affichage uniquement utile à des fins de débug
                logger.info(f"{nom_departement} terminé, on commence l'insertion dans le csv")



                # On génère le fake code insee
                
                # Si le numéro de département est à 2 chiffres on rajoute 999
                if len(numero_departement)==2:
                    fake_insee=str(numero_departement)+"999"

                # Si le numéro de département est à 3 chiffres on rajoute 99 (DOM/TOM)
                elif len(numero_departement)==3:
                    fake_insee=str(numero_departement)+"99"

                # Sinon, on a un soucis
                else:
                    logger.info("erreur avec le code du département")


                # Le champ gid présent dans le csv data gouv est utilisé, on le randomise au moment de l'insertion dans le csv pour pouvoir faire du débug

                # On ouvre le fichier CSV en mode append pour ne pas effacer les lignes à chaque repassage dans la boucle
                with open('./data/input/centres_doctolib_scrape'+csv_varname+'.csv', mode='a',encoding='utf-8') as fichier_csv:
                    ecriture_csv = csv.writer(fichier_csv, delimiter=';', lineterminator='\n', quoting=csv.QUOTE_MINIMAL)

                    # Pour chaque centre de la liste
                    for centre in array_centres_dep:
                        
                            # On écrit dans le fichier csv le nom du centre, le code_insee, l'url de prise de rdv et le fake gid
                            ecriture_csv.writerow([random.randint(1000,9999),centre,fake_insee,array_centres_dep[centre]])

                    # Affichage uniquement utile à des fins de débug
                    logger.info("département bien inséré dans le csv")





if __name__ == "__main__":
        main()
