# project specific
import scrapy
from scrapy import Spider, Request
# external packages imports
import pdb
import requests
# python packages imports
from pprint import pprint
import logging
logging.debug("This is a warning")


class PlanningSpider(Spider):
    name = "planning"
    base_url = "https://publicaccess.nottinghamcity.gov.uk/online-applications/search.do?action=monthlyList"
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en,fr;q=0.8,fr-FR;q=0.5,en-US;q=0.3",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "Pragma": "no-cache",
        "Upgrade-Insecure-Requests": 1,
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:89.0) Gecko/20100101 Firefox/89.0"
    }

    def start_requests(self):
        yield Request(url=self.base_url, callback=self.parse_parameters, headers=self.headers)

    def parse_parameters(self, res):
        token = res.css('input[type="hidden"]').css('::attr(value)').get()

        return scrapy.FormRequest.from_response(
            res,
            formdata={'searchCriteria.ward': '', 'month': 'Aug+21',
                      'dateType': 'DC_Validated', 'searchType': 'Application', "_csrf": token},
            callback=self.test
        )

    def test(self, res):

        pdb.set_trace()

# https://publicaccess.nottinghamcity.gov.uk/online-applications/monthlyListResults.do?action=firstPage


# org.apache.struts.taglib.html.TOKEN = 4660f0c3e43db13761d19669438db6f2 & _csrf = 91ceb883-fa8d-423d-be56-51618fd69f9a & searchCriteria.ward = &month = Aug+21 & dateType = DC_Validated & searchType = Application
