# project specific
from utilities import get_country, combine_items, get_currency, get_tenancy_type, get_room_type, pw_to_pm, weeks_to_months
from items import BuildingItem, RoomItem, CombinedItem, ContractItem
from scrapy import Spider, Request, FormRequest
# external packages imports
import pdb
# python packages imports
from datetime import datetime, timedelta
import logging
logging.debug("This is a warning")


class StudentCastleSpider(Spider):
    name = "studentcastle"
    base_url = 'https://www.studentcastle.co.uk/'
    headers = {
        'Accept': 'image/webp,*/*',
        'Accept-Encoding': 'gzip, deflate, br',
        'Accept-Language': 'en,fr;q=0.8,fr-FR;q=0.5,en-US;q=0.3',
        'Connection': 'keep-alive',
        'Pragma': 'no-cache',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.16; rv:86.0) Gecko/20100101 Firefox/86.0',
        'X-Requested-With': 'XMLHttpRequest'
    }

    def start_requests(self):
        yield Request(url=self.base_url, callback=self.parse_city, headers=self.headers)

    def parse_city(self, res):
        cities_url = [valid_url for valid_url in res.css('div.footer').css(
            'li a::attr(href)').getall() if "student-accommodation" in valid_url]

        for city_url in cities_url:
            url = self.base_url + city_url[1:]
            yield Request(url=url, callback=self.parse_building, dont_filter=True, headers=self.headers)

    def parse_building(self, res):
        description = res.css('div[id="page_content"]').css(
            'div.section_title').css('p::text').get().strip()
        description = description.replace('\n', '').replace('\r', ' ').strip()
        building_item = BuildingItem({
            "description": description,
            "url": res.url,
            "operator": "Student Castle",
        })

        location_url = res.url + 'location/'
        bookings_url = res.url + 'rooms-booking/'
        yield Request(url=location_url, callback=self.parse_location, meta={"building_item": building_item, "bookings_url": bookings_url}, headers=self.headers, dont_filter=True)

    def parse_location(self, res):
        building_item = res.meta["building_item"]
        bookings_url = res.meta["bookings_url"]

        city = res.css('div.map_palm').css('h3::text').get()
        coordinates = res.css('div.map_palm::attr(style)').get().split(
            'staticmap?center=')[-1].split('&zoom=')[0]

        building_item.update({
            "name": "Student Castle " + city.title(),
            "city": city,
            "address": " ".join([element.replace("&nbsp;", " ").replace('\n', '').replace('\t', '').replace('\xa0', ' ') for element in res.css(
                'div.map_palm').css('p *::text').getall()]),
            "longitude": coordinates.split(',')[1],
            "latitude": coordinates.split(',')[0]
        })

        # country
        building_item["country"] = get_country(
            building_item["latitude"], building_item["longitude"])

        yield Request(url=bookings_url, callback=self.parse_booking_page, headers=self.headers, meta={"building_item": building_item})

    def parse_booking_page(self, res):
        building_item = res.meta["building_item"]

        contract_dict = {
            "offers": res.css('div[id="demobox"]').css('a::text').getall()
        }
        urls_all = res.css('div.wrapper > ul.list_reset').css(
            'li a::attr(href)').getall()
        urls__academic_year = [url for url in urls_all if 'acYear' in url]

        for academic_year in urls__academic_year:
            url = res.url + academic_year
            yield Request(url=url, callback=self.parse_booking, headers=self.headers, meta={"contract_dict": contract_dict, "building_item": building_item})

    def parse_booking(self, res):
        building_item = res.meta["building_item"]
        contract_dict = res.meta["contract_dict"]

        rooms = dict()

        for price_url in res.css('ul.list_reset').css('li a.btn_occupancy::attr(href)').getall():
            url = self.base_url + price_url[1:]
            yield Request(url=url, callback=self.parse_room, headers=self.headers, meta={"contract_dict": contract_dict, "building_item": building_item})

    def parse_room(self, res):
        building_item = res.meta["building_item"]
        contract_dict = res.meta["contract_dict"]

        btn_occupancy = res.css('div.dropdown_room_detail').css(
            'ul[id="roomOccumpancy"]')
        room_id = btn_occupancy.css(
            'li::attr(data-roomtype-id)').get()
        occupancies = btn_occupancy.css('li::attr(data-occumpancy-id)').getall()
        academic_year = btn_occupancy.css('li::attr(data-year)').get()

        btn_tenancy = res.css('div.dropdown_room_detail').css(
            'ul[id="roomContract"]')
        tenancies = list()
        for element in btn_tenancy.css('li'):
            tenancies.append({
                "tenancy": element.css('::attr(data-contract-weeks)').get(),
                "date_start": element.css('::attr(data-contract-leasestart)').get()
            })

        for occupancy in occupancies:
            for contract in tenancies:

                amenities = list()
                for element in res.css('div.push_lap_1_8'):
                    title = element.css('h4::text').get()
                    try:
                        if 'studio' in title or 'flat' in title:
                            amenities.append(element.css('ul').css('li').css(
                                'button::text').getall())
                    except TypeError:
                        pass

                room_item = RoomItem({
                    "building_name": building_item["name"],
                    "operator": building_item["operator"],
                    "description": res.css('div.section').css('div.wrapper').css('div.section_title').css('p.standfirst::text').get().strip(),
                    "amenities": amenities[0],
                    "name": res.css('div.section').css('div.wrapper').css('div.section_title').css('h2::text').get(),
                    "url": res.url,
                })

                contract_item = ContractItem({
                    "building_name": building_item["name"],
                    "room_name": room_item["name"],
                    "academic_year": f'{academic_year.split("-")[0]}/20{academic_year.split("-")[-1]}',
                    "date_start": datetime.strptime(contract["date_start"], '%Y-%m-%d').date(),
                    "offers": contract_dict["offers"],
                    "tenancy_weeks": int(contract["tenancy"]),
                    "tenancy_months": weeks_to_months(int(contract["tenancy"])),
                    "url": res.url,
                    # "availability": "sold out",
                    # "rent_pw": "n/a",
                    # "rent_pm": "n/a",
                    # "rent_total": "n/a"
                })

                # room type
                room_item["type"] = get_room_type(room_item['name'])

                # contract_item tenancy_type
                contract_item["tenancy_type"] = get_tenancy_type(
                    contract_item["tenancy_weeks"])

                # payload
                payload = {
                    "roomTypeId": room_id,
                    "occupancy": occupancy,
                    "academicYear": academic_year,
                    "contractWeeks": contract["tenancy"],
                    "leaseStart": contract["date_start"],
                    "section": "RoomPriceDetail"
                }

                url = "https://www.studentcastle.co.uk/umbraco/surface/RoomPrice/RoomPrice"
                yield FormRequest(url=url, callback=self.parse_room_price, method="POST", formdata=payload, headers=self.headers, meta={"room_item": room_item, "building_item": building_item, "payload": payload, "contract_item": contract_item}, dont_filter=True)

        yield building_item

    def parse_room_price(self, res):
        building_item = res.meta["building_item"]
        room_item = res.meta["room_item"]
        contract_item = res.meta["contract_item"]

        contract = {}
        contract_length = None
        for line in res.css('table').css('tr'):
            line_element = line.css('td::text').getall()
            if line_element[0].lower() == 'contract length':
                contract_length = line_element[-1].lower()
            elif line_element[0].lower() == 'booking fee':
                contract["booking_fee"] = float(
                    line_element[-1].lower().strip('£'))
            elif line_element[0].lower() == 'cost per week':
                contract["rent_pw"] = float(line_element[-1].lower().strip('£'))
            else:
                pass

        if contract_length:
            start = contract_length.find("to ") + len("to ")
            contract__date_end = contract_length[start:].replace(
                ")", "").strip()
            contract__date_end = datetime.strptime(
                contract__date_end, '%d/%m/%Y').date()

            contract_item.update({
                "rent_pw": float(contract["rent_pw"]),
                "date_end": contract__date_end,
                "booking_fee": int(contract["booking_fee"]),
                "availability": "available"
            })

            # rents
            contract_item.update({
                "rent_pw": float(contract["rent_pw"]),
                "rent_pm": pw_to_pm(float(contract["rent_pw"]))
            })

            # currency
            contract_item["currency"] = get_currency(
                building_item["country"])

            # room available
            room_item["availability"] = "available"

            # total rent
            contract_item["rent_total"] = contract_item["rent_pw"] * \
                contract_item["tenancy_weeks"]

        else:
            # contract end date
            contract__date_end = contract_item["date_start"] + \
                timedelta(days=7 * contract_item["tenancy_weeks"])
            contract_item["date_end"] = contract__date_end

        # combined_item
        combined_item = CombinedItem()
        combined_item_info = combine_items(
            building_item, room_item, contract_item)
        combined_item.update(combined_item_info)

        yield room_item
        yield combined_item
        yield contract_item
