# project specific
from utilities import get_country, combine_items, get_currency, get_room_type, get_tenancy_type, days_to_weeks, days_to_months, pw_to_pm
from items import BuildingItem, CampusItem, CombinedItem, ContractItem, RoomItem
from scrapy import Spider, Request
# external packages imports
import requests
import pdb
# python packages imports
from datetime import datetime
import logging
logging.debug("This is a warning")


class CrmSpider(Spider):
    name = "crm"
    base_url = 'https://www.crm-students.com'

    def start_requests(self):
        url = f'{self.base_url}/locations/'
        yield Request(url=url, callback=self.parse_cities)

    def parse_cities(self, res):
        for element in res.css('div[id="cities"]').css('a'):
            city = {
                "name": element.css('div.content').css('span.title::text').get(),
                "url": element.css('::attr(href)').get()
            }
            yield Request(url=city["url"], callback=self.parse_properties, meta={"city": city})

    def parse_properties(self, res):
        # parse scheme
        for property in res.css('div[id="propertyContent"]').css('div.property'):
            property_url = property.css('a::attr(href)').get()
            yield Request(url=property_url, callback=self.parse_scheme, meta={"city": res.meta["city"]}, dont_filter=True)

        # parse campus
        for campus in res.css('div[id="uniContainer"]').css('div.card'):
            text_description = " ".join(campus.css(
                'p *::text').getall())

            campus_item = CampusItem({
                "name": campus.css('p.title::text').get(),
                "institution": campus.css('p.title::text').get(),
                "city": res.meta["city"]["name"],
            })

            # campus address
            if "address" in text_description.lower():
                campus_item["address"] = [text.split("Address:")[-1]
                                          for text in campus.css('p::text').getall() if "Address" in text][0].strip()

            # coordinates
            latitude = campus.css('::attr(data-lat)').get()
            longitude = campus.css('::attr(data-lng)').get()
            if len(latitude) == 0:
                try:
                    postcode = campus_item["address"].split(",")[-1].strip()
                    url_coordinates = f'https://postcodes.io/postcodes/{postcode}'
                    request = requests.get(url_coordinates)
                    latitude = request.json()["result"]["latitude"]
                    longitude = request.json()["result"]["longitude"]
                except:
                    postcode = f'{campus_item["address"].split(" ")[-2]} {campus_item["address"].split(" ")[-1]}'
                    url_coordinates = f'https://postcodes.io/postcodes/{postcode}'
                    request = requests.get(url_coordinates)
                    latitude = request.json()["result"]["latitude"]
                    longitude = request.json()["result"]["longitude"]

            campus_item.update({
                "latitude": float(latitude),
                "longitude": float(longitude)
            })

            yield campus_item

    def parse_scheme(self, res):

        city = res.meta["city"]["name"]
        address_texts = res.css(
            'section[id="overview"]').css('div.address').css('p::text').getall()
        address = " ".join([element.strip()
                            for element in address_texts if element])

        description = " ".join([element.strip()
                                for element in res.css(
            'section.about').css('div.row').css('div.col-7').css('p::text').getall()])

        building_item = BuildingItem({
            "name": res.css('header').css('h1::text').get().split("-")[0].strip(),
            "address": address,
            "city": city,
            "description": description,
            "url": res.url,
            "operator": "CRM Students",
        })

        # coordinates
        latitude = res.css('input[id="mapLocationLat"]::attr(value)').get()
        longitude = res.css('input[id="mapLocationLng"]::attr(value)').get()

        if len(latitude) == 0:
            postcode = address.split(',')[-1].strip()
            url_coordinates = f'https://postcodes.io/postcodes/{postcode}'
            request = requests.get(url_coordinates)
            latitude = float(request.json()["result"]["latitude"])
            longitude = float(request.json()["result"]["longitude"])

        building_item.update({
            "latitude": float(latitude),
            "longitude": float(longitude)
        })

        # country
        building_item["country"] = get_country(
            building_item["latitude"], building_item["longitude"])

        # offers
        offers = "n/a"
        offers_description = ". ".join(filter(None, [element.replace('\n', '').strip() for element in res.css(
            'ul.promo-banner__items').css('li *::text').getall() if element != "Find out more"])).strip()
        if offers_description:
            offers = offers_description

        if res.css('div.property-ctas').css('a::attr(href)').get():
            room_url = res.css('div.property-ctas').css('a::attr(href)').get()
            if self.base_url in room_url:
                room_list_url = room_url
            else:
                room_list_url = f"{self.base_url}{room_url}"

            yield Request(url=room_list_url, callback=self.room_urls, meta={"building_item": building_item, "offers": offers})

        yield building_item

    def room_urls(self, res):
        building_item = res.meta["building_item"]
        offers = res.meta["offers"]

        u = res.url.split("config_year=")[0]
        for element in res.css('div.configYears').css('label'):

            value = element.css('::attr(for)').get()
            room_list_url = f'{u}config_year={value}'
            academic_year = element.css('::text').get()

            yield Request(url=room_list_url, callback=self.parse_contracts, meta={"academic_year": academic_year, "building_item": building_item, "offers": offers}, dont_filter=True)

    def parse_contracts(self, res):
        building_item = res.meta["building_item"]
        academic_year = res.meta["academic_year"]
        offers = res.meta["offers"]

        # room descriptions
        room_described = res.css(
            'div[id="room-details"]').css('h3.room-title::text').get()

        room_description = res.css(
            'div[id="room-details"]').css('section[id="included"]').css('p::text').get()
        if not room_description:
            room_description = "n/a"

        # room amenities
        room_amenities = res.css(
            'div[id="room-details"]').css('section[id="description"]').css('li::text').getall()
        room_amenities = [element.replace("\n", "")
                          for element in room_amenities]
        room_amenities = " ".join(
            element for element in room_amenities if element)
        if len(room_amenities) == 0:
            room_amenities = "n/a"

        for element in res.css('aside.miniCards').css('a'):

            date_start = element.css('::attr(data-start-date)').get().split(',')
            date_end = element.css('::attr(data-end-date)').get().split(',')

            for k in range(len(date_start)):
                room_item = RoomItem({
                    "building_name": building_item["name"],
                    "operator": building_item["operator"],
                    "name": element.css('::attr(data-title)').get(),
                    "url": res.url,
                    "availability": "available",
                })

                # room type
                room_item["type"] = get_room_type(room_item['name'])

                # room amenities
                if room_described == room_item["name"]:
                    room_item["description"] = room_description
                    room_item["amenities"] = room_amenities

                # contract_item
                contract_item = ContractItem({
                    "building_name": building_item["name"],
                    "room_name": room_item["name"],
                    # "date_start": "n/a",
                    # "date_end": "n/a",
                    "availability": "available",
                    "academic_year": academic_year,
                    "url": res.url,
                    "offers": offers,
                    # "tenancy_type": "n/a",
                    # "tenancy_weeks": "n/a",
                    # "rent_pw": "n/a",
                    # "rent_total": "n/a",
                    # "currency": "n/a"
                })

                # tenancy start and end date
                date_start_k = date_start[k]
                date_end_k = date_end[k]
                if date_start_k:
                    contract_item["date_start"] = datetime.strptime(
                        date_start_k, '%Y-%m-%d').date()
                    contract_item["date_end"] = datetime.strptime(
                        date_end_k, '%Y-%m-%d').date()

                rent = element.css('::attr(data-price-per-week)').get()
                if len(rent) != 0 and date_start_k == 0:
                    contract_item["date_start"] = datetime(
                        int(academic_year.split('/')[0]), 9, 18).date()
                    contract_item["date_end"] = datetime(
                        int(academic_year.split('/')[1]), 9, 9).date()

                if contract_item.get("date_start") is not None:

                    # tenancy
                    contract_item["tenancy_weeks"] = days_to_weeks(
                        contract_item["date_start"], contract_item["date_end"])
                    contract_item["tenancy_months"] = days_to_months(
                        contract_item["date_start"], contract_item["date_end"])

                    # tenancy type
                    contract_item["tenancy_type"] = get_tenancy_type(
                        contract_item["tenancy_weeks"])

                    # rent
                    rent = float(rent.replace(",", ""))
                    if int(rent) != 0:
                        contract_item["rent_pw"] = rent
                        contract_item["rent_pm"] = pw_to_pm(rent)
                        contract_item["rent_total"] = contract_item["tenancy_weeks"] * \
                            contract_item["rent_pw"]

                    # currency
                    contract_item["currency"] = get_currency(
                        building_item["country"])

                    # combined item
                    combined_item = CombinedItem()
                    combined_item_info = combine_items(
                        building_item, room_item, contract_item)
                    combined_item.update(combined_item_info)

                else:
                    room_item["availability"] = "sold out"
                    contract_item["availability"] = "sold out"

                    # combined item
                    combined_item = CombinedItem()
                    combined_item_info = combine_items(
                        building_item, room_item)
                    combined_item.update(combined_item_info)

                yield contract_item
                yield combined_item
                yield room_item
