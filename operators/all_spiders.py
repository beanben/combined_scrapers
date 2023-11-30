# import scrapy
from twisted.internet import reactor, defer
from scrapy.crawler import CrawlerRunner
from scrapy.utils.log import configure_logging
from scrapy.utils.project import get_project_settings

# import spiders
from spiders.crm import CrmSpider
from spiders.fresh import FreshSpider
from spiders.hello_students import HelloStudentSpider
from spiders.homes4students import Homes4StudentsSpider
from spiders.host import HostSpider
from spiders.iq_student import IqStudentSpider
from spiders.livensa import LivensaSpider
from spiders.nexo import NexoSpider
from spiders.prestige import PrestigeSpider
from spiders.resa import ResaSpider
from spiders.scape import ScapeSpider
from spiders.student_housing import StudentHousingSpider
from spiders.student_roost import StudentRoostSpider
from spiders.studentcastle import StudentCastleSpider
from spiders.unite import UniteSpider

from spiders.planning import PlanningSpider

# imports for sending email
import os
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Content
from datetime import datetime
from dotenv import dotenv_values

# spiders
settings = get_project_settings()
configure_logging(settings)
runner = CrawlerRunner(settings)


@defer.inlineCallbacks
def crawl():
    # <------ Spider used to set up csv headers ------>
    # yield runner.crawl(IqStudentSpider)

    # <------ Private spiders ------>
    # yield runner.crawl(CrmSpider)
    # yield runner.crawl(FreshSpider)
    # yield runner.crawl(HelloStudentSpider)
    # yield runner.crawl(Homes4StudentsSpider)
    # yield runner.crawl(HostSpider)
    # yield runner.crawl(PrestigeSpider)
    # yield runner.crawl(ScapeSpider)
    # yield runner.crawl(StudentRoostSpider)
    # yield runner.crawl(StudentCastleSpider)
    yield runner.crawl(UniteSpider)
    # yield runner.crawl(StudentHousingSpider)

    # <------ Spain ------>
    # yield runner.crawl(LivensaSpider)
    # yield runner.crawl(NexoSpider)
    # yield runner.crawl(ResaSpider)

    # <------ Planning info ------>
    # yield runner.crawl(PlanningSpider)

    reactor.stop()


# email on finish
def send_email():
    # get api_key
    file_name = 'sendgrid.env'
    path_to_file = f'{os.path.dirname(os.getcwd())}/{file_name}'
    config = dotenv_values(path_to_file)
    api_key = config["SENDGRID_API_KEY"]

    # send message
    timing = datetime.now().strftime('%Y-%m-%d %H:%M')
    message = Mail(
        from_email='benoit.fesquet@edhec.com',
        to_emails='benoit.fesquet@edhec.com',
        subject=f"Scraper Finished at {timing}",
        html_content='<strong>-</strong>'
    )
    sg = SendGridAPIClient(api_key)
    response = sg.send(message)


crawl()
reactor.run()
# send_email()
