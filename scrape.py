from multiprocessing import freeze_support

from scraper.scraper import main

if __name__ == "__main__":
    freeze_support()
    main()
