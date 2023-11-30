from scrapy.exporters import CsvItemExporter
from scrapy import signals
from scrapy.exceptions import DropItem

from pydispatch import dispatcher
import datetime
import pdb
import os.path

current_date = datetime.datetime.today().strftime("%Y%m%d")
count_spiders = 0


def item_type(item):
    return type(item).__name__.replace('Item', '').lower()  # TeamItem => team


def _doesnt_exist(path):
    return (not os.path.isfile(path))


class MultiCSVItemPipeline(object):
    SaveTypes = ['room', 'building', 'campus',
                 'contract', 'venue', 'combined']
    CSVDir = './output/'+current_date+'_'

    def __init__(self):
        dispatcher.connect(self.spider_opened, signal=signals.spider_opened)
        dispatcher.connect(self.spider_closed, signal=signals.spider_closed)

        self.campus_seen = set()
        self.buildings_seen = set()
        self.room_seen = set()
        self.contract_seen = set()
        self.venues_seen = set()
        self.combined_seen = set()

    def spider_opened(self, spider):
        # csv headers genmerated by the first spider only.
        include_headers = True
        global count_spiders
        count_spiders += 1
        if count_spiders > 1:
            include_headers = False
        # pdb.set_trace()

        try:
            self.files = dict([(name, open(f'{self.CSVDir}{name}.csv', 'a+b'))
                               for name in self.SaveTypes])
        except:
            self.files = dict([(name, open(f'{self.CSVDir}{name}.csv', 'w+b'))
                               for name in self.SaveTypes])
        self.exporters = dict(
            [(name, CsvItemExporter(self.files[name], include_headers_line=include_headers)) for name in self.SaveTypes])
        [e.start_exporting() for e in self.exporters.values()]

    def spider_closed(self, spider):
        [e.finish_exporting() for e in self.exporters.values()]
        [f.close() for f in self.files.values()]

    def process_item(self, item, spider):

        # set defaults in case no values returned
        for field in item.fields:
            item.setdefault(field, 'n/a')
            if item[field] is None:
                item[field] = "n/a"

        # drop duplicates
        what = item_type(item)

        if what == "building":
            building_info = (item["latitude"], item["longitude"], item["name"])
            if building_info in self.buildings_seen:
                raise DropItem(f"building duplicated")
            else:
                self.buildings_seen.add(building_info)

        elif what == "venue":
            if item["name"] in self.venues_seen:
                raise DropItem(f"venue duplicated")
            else:
                self.venues_seen.add(item["name"])

        elif what == "room":
            room_info = (
                item["building_name"],
                item["operator"],
                item["name"]
            )
            if room_info in self.room_seen:
                raise DropItem(f"room duplicated")
            else:
                self.room_seen.add(room_info)

        elif what == "contract":
            contract_info = (
                item["building_name"],
                item["room_name"],
                item["academic_year"],
                item["tenancy_weeks"],
                item["rent_pw"],
                item["date_start"]
            )
            if contract_info in self.contract_seen:
                raise DropItem(f"contract duplicated")
            else:
                self.contract_seen.add(contract_info)

        elif what == "combined":
            combined_info = (
                item["operator"],
                item["building_name"],
                item["latitude"],
                item["longitude"],
                item["room_name"],
                item["academic_year"],
                item["tenancy_weeks"],
                item["rent_pw"],
                item["contract__date_start"]
            )
            if combined_info in self.combined_seen:
                raise DropItem(f"combined duplicated")
            else:
                self.combined_seen.add(combined_info)

        elif what == "campus":
            campus_info = (
                item["name"]
            )
            if campus_info in self.campus_seen:
                raise DropItem(f"campus duplicated")
            else:
                self.campus_seen.add(campus_info)
        else:
            pass

        if what in self.SaveTypes:
            self.exporters[what].export_item(item)

        return item
