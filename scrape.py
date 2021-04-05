from multiprocessing import freeze_support

from scraper import main, export_centres_stats

if __name__ == '__main__':
    freeze_support()
    main()
