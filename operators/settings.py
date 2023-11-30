import requests
import time


def proxy_list():
    proxies_url = 'https://api.proxyscrape.com/?request=getproxies&proxytype=http&timeout=10000&country=all&ssl=yes&anonymity=elite'
    res = requests.get(proxies_url)
    proxies_list = res.content.decode("utf-8").splitlines()

    proxies = ''
    filename = 'proxies.txt'

    with open(filename, 'r') as text_file:
        proxies = text_file.readlines()

    if len(proxies) == 0:
        open(filename, 'wb').write(res.content)
    else:
        print('\n')
        print('first proxy in list - before refresh:', proxies_list[0])
        while proxies_list[0] == proxies[0].strip():
            # wait for the website with free proxies to refresh the list of free proxies available
            print('sleep 30 sec..')
            time.sleep(30)
            # refresh list of free proxies
            res = requests.get(proxies_url)
            proxies_list = res.content.decode("utf-8").splitlines()

        print('....proxy list refreshed')
        print('first proxy in list - after refresh:', proxies_list[0])
        open(filename, 'wb').write(res.content)

    return filename


BOT_NAME = 'operators'
SPIDER_MODULES = ['operators.spiders']
NEWSPIDER_MODULE = 'operators.spiders'
ROBOTSTXT_OBEY = False
# DOWNLOAD_DELAY = 0.5
RANDOMIZE_DOWNLOAD_DELAY = True
USER_AGENT_LIST = "user-agent.txt"
RETRY_HTTP_CODES = [403, 524, ]
RETRY_TIMES = 5
# CLOSESPIDER_PAGECOUNT = 30
# CONCURRENT_REQUESTS = 1

# logging
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s - %(levelname)s: %(message)s"
LOG_DATEFORMAT = '%Y-%m-%d %H:%M'
LOG_FILE = "log.txt"

DOWNLOADER_MIDDLEWARES = {
    'operators.middlewares.OperatorsDownloaderMiddleware': 543,
    'scrapy.downloadermiddlewares.useragent.UserAgentMiddleware': None,
    'random_useragent.RandomUserAgentMiddleware': 400,
    'rotating_proxies.middlewares.RotatingProxyMiddleware': 610,
    'rotating_proxies.middlewares.BanDetectionMiddleware': 620
}
ITEM_PIPELINES = {
    'operators.pipelines.MultiCSVItemPipeline': 300,
}
# ROTATING_PROXY_LIST_PATH = proxy_list()
ROTATING_PROXY_LIST_PATH = None
