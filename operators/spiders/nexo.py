# project specific
from utilities import get_address, get_city, get_room_type, get_tenancy_type, days_to_weeks, days_to_months, combine_items, get_country, get_currency, pm_to_pw
from items import CampusItem, BuildingItem, RoomItem, ContractItem, CombinedItem, VenueItem
from scrapy import Spider, Request
# external packages imports
import requests
import pdb
from urllib import parse
from unidecode import unidecode
# python packages imports
from datetime import datetime
import json
import logging
logging.debug("This is a warning")


class NexoSpider(Spider):
    name = "nexo"
    base_url = 'https://nexoresidencias.com'
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        # "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "en,fr;q=0.8,fr-FR;q=0.5,en-US;q=0.3",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        # "Host": "https://host-students.com/",
        "Pragma": "no-cache",
        "Upgrade-Insecure-Requests": 1,
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:89.0) Gecko/20100101 Firefox/89.0"
    }
    index_proxy = 0

    def start_requests(self):
        url_spain = f'{self.base_url}/en/global/spain'

        yield Request(url=url_spain, callback=self.parse_cities, headers=self.headers)

    def parse_cities(self, res):
        for bullet in res.css('ul.category-tiles__list').css('li'):

            # url city
            link_city = bullet.css('a::attr(href)').get()
            url_city = f'{self.base_url}{link_city}'

            # city name & url
            city = {
                "name": bullet.css('span.category-tiles__item-title::text').get(),
                "url": url_city
            }

            yield Request(url=city["url"], callback=self.parse_properties, meta={"city": city}, headers=self.headers)

    def parse_properties(self, res):
        city = res.meta['city']

        # schemes coordinates
        map_link = res.css(
            'div.js-google-maps').css('::attr(data-info-link)').get()
        coordinates_link = f'{self.base_url}{map_link}'

        response = requests.get(coordinates_link)

        building_coordinates = {}
        for scheme in response.json()["markers"]:
            scheme_name = unidecode(scheme["title"])
            building_coordinates[scheme_name] = {
                "latitude": scheme["lat"],
                "longitude": scheme["lng"]
            }

        for element in res.css('div.comparison-carousel__wrapper').css('article'):
            building_item = BuildingItem({
                "city": unidecode(city["name"]),
                "description": unidecode(element.css('p::text').get().strip()),
                "operator": "Nexo Residencias"
            })

            # description
            description = element.css('div.comparison-carousel__item-info').css(
                'div.comparison-carousel__item-text').css('p::text').get()
            if description:
                building_item["description"] = description.strip()

            # url property
            link_property = element.css(
                'a.comparison-carousel__item-link::attr(href)').get()
            if link_property:
                building_item["url"] = f'{self.base_url}{parse.unquote(link_property)}'

            try:
                yield Request(url=building_item["url"], callback=self.parse_scheme, meta={"building_item": building_item, "building_coordinates": building_coordinates}, headers=self.headers, dont_filter=True)
            except:
                pass

    def parse_scheme(self, res):
        building_item = res.meta['building_item']
        building_coordinates = res.meta["building_coordinates"]

        # building name
        building_item["name"] = res.css(
            'div.residence__main-info').css('h1.residence__title::text').get()
        building_item["name"] = unidecode(building_item["name"])

        # building_coordinates
        building_name = building_item["name"]
        building_name_adj = [
            element for element in building_coordinates.keys() if element in building_name]
        if building_name_adj:
            building_name = building_name_adj[0]
        building_name = unidecode(building_name)
        building_item.update({
            "latitude": float(building_coordinates[building_name]["latitude"]),
            "longitude": float(building_coordinates[building_name]["longitude"]),
        })
        # country
        building_item["country"] = get_country(
            building_item["latitude"], building_item["longitude"])

        # additional description
        addtl_descr = res.css('div.residence__description').css(
            'p::text').getall()
        addtl_descr = " ".join([element for element in addtl_descr if element])
        building_item["description"] = " ".join(
            [building_item["description"], addtl_descr])

        # contract utilities_included
        elements_included = res.css('section.icon-logo--type5 *::text').getall()
        elements_included = [elements.replace("\r", "").replace(
            "\n", "").strip() for elements in elements_included]
        elements_included = [
            elements for elements in elements_included if elements]

        contract_utilities = []
        for el in elements_included:
            if el == "And more...":
                break
            if el != "What's included":
                contract_utilities.append(el)

        # facilities
        facilities_1 = res.css(
            'section.icon-logo--type1-2').css('article.icon-logo__item').css('h6::text').getall()
        facilities_1 = [element.replace("\n", "").replace(
            "\r", "") for element in facilities_1]

        facilities_2 = list(set(elements_included) - set(contract_utilities))
        facilities_2.remove("What's included")
        facilities_2.remove("And more...")

        building_item["facilities"] = facilities_1 + facilities_2

        # venues & universities
        map_link = res.css(
            'div.js-google-maps').css('::attr(data-info-link)').get()
        coordinates_link = f'{self.base_url}{map_link}'

        response = requests.get(coordinates_link)

        for scheme in response.json()["markers"]:
            if scheme["type"] == "universities":
                campus_item = CampusItem({
                    "name": scheme["title"],
                    "latitude": float(scheme["lat"].replace(",", "")),
                    "longitude": float(scheme["lng"].replace(",", ""))
                })
                campus_item.update({
                    "institution": campus_item["name"],
                    "address": get_address(
                        campus_item["latitude"], campus_item["longitude"]),
                    "city": get_city(campus_item["latitude"], campus_item["longitude"])
                })
                yield campus_item
            else:
                venue_item = VenueItem({
                    "type": scheme["type"],
                    "latitude": float(scheme["lat"].replace(",", "")),
                    "longitude": float(scheme["lng"].replace(",", "")),
                    "name": scheme["title"],
                })
                venue_item["city"] = get_city(
                    venue_item["latitude"], venue_item["longitude"])
                yield venue_item

        # contract_offers
        contract_offers = res.css('div.js-text-banner::attr(data-gtm-id)').get()
        contract_offers = contract_offers.replace("EN", "").strip()

        # room_links
        url_rooms = f'{res.url}/rooms'
        yield Request(url=url_rooms, callback=self.parse_room_list, meta={
            "building_item": building_item,
            "contract_offers": contract_offers
        }, dont_filter=True)

    def parse_room_list(self, res):
        building_item = res.meta["building_item"]
        contract_offers = res.meta["contract_offers"]

        # script extract
        script = res.css('script').getall()
        script = [
            element for element in script if "searchData.results" in element][0]
        start = script.find("searchData.results = ") + \
            len("searchData.results = ")
        end = script.find(";\r\n</script>")
        script = script[start:end]
        script = json.loads(script)

        for room in script["groups"][0]["roomTypes"]:

            # room_item
            room_item = RoomItem({
                "name": unidecode(room["name"]),
                "operator": building_item["operator"],
                "building_name": building_item["name"],
                "url": unidecode(room["link"])
            })

            yield Request(url=room_item["url"], callback=self.parse_room, meta={
                "building_item": building_item,
                "room_item": room_item,
                "contract_offers": contract_offers
            }, dont_filter=True)

    def parse_room(self, res):
        building_item = res.meta["building_item"]
        room_item = res.meta["room_item"]
        contract_offers = res.meta["contract_offers"]

        # room description
        room_item["description"] = res.css(
            'div.product__description').css('p::text').get()

        # building_address
        building_item["address"] = res.css(
            'div.residence__contact-details').css('p::text').get()
        building_item["address"] = unidecode(building_item["address"])

        # room amenities
        amenities = res.css(
            'section.icon-logo--type1-2').css('article.icon-logo__item').css('h6::text').getall()
        amenities = [element.replace("\r", "").replace("\n", "")
                     for element in amenities]
        room_item["amenities"] = amenities

        # room type
        room_item["type"] = get_room_type(
            room_item["name"], room_item["amenities"])

        # contract utilities_included
        contract_utilities = res.css(
            'section.icon-logo--type5').css('article.icon-logo__item').css('h6::text').getall()
        contract_utilities = [element.replace("\r", "").replace(
            "\n", "") for element in contract_utilities]

        # room availability
        room_sold_out = res.css('div.product__details').css(
            'div.product__soldout-message::text').get()
        room_item["availability"] = (
            "sold out" if room_sold_out else "available")
        # if room_sold_out:
        #     room_item["availability"] = "sold out"

        # contract_info
        contract_info = {
            "building_name": building_item["name"],
            "offers": contract_offers,
            "utilities_included": contract_utilities,
            "room_name": room_item["name"],
            "url": res.url,
            "availability": room_item["availability"],
            "currency": get_currency(
                building_item["country"])
        }

        # url_contract info
        url_contract_info = res.css(
            'tenancy-options::attr(tenancies-link)').get()

        if url_contract_info:
            url_contract = f'{self.base_url}{url_contract_info}'

            yield Request(url=url_contract, callback=self.parse_contract, meta={
                "room_item": room_item,
                "building_item": building_item,
                "contract_info": contract_info
            }, dont_filter=True)

        else:
            # combined_item
            combined_item = CombinedItem()
            combined_item_info = combine_items(building_item, room_item)
            combined_item.update(combined_item_info)
            yield combined_item
            yield room_item
            yield building_item

    def parse_contract(self, res):
        room_item = res.meta["room_item"]
        building_item = res.meta["building_item"]
        contract_info = res.meta["contract_info"]

        response = res.json()

        # tenancies
        for tenancies in response["tenancy-options"]:
            contract_item = ContractItem()
            contract_item.update(contract_info)

            # academic_year
            start_year = tenancies["fromYear"]
            end_year = tenancies["toYear"]
            contract_item["academic_year"] = f'{start_year}/{end_year}'

            # date_start
            date_start = tenancies["tenancyOption"][0]["startDate"]
            date_start = datetime.strptime(date_start, "%Y-%m-%d")
            contract_item["date_start"] = date_start.date()

            # date_end
            date_end = tenancies["tenancyOption"][0]["endDate"]
            date_end = datetime.strptime(date_end, "%Y-%m-%d")
            contract_item["date_end"] = date_end.date()

            # tenancy_weeks
            contract_item["tenancy_weeks"] = days_to_weeks(date_start, date_end)

            # tenancy_months
            contract_item["tenancy_months"] = days_to_months(
                date_start, date_end)

            # tenancy_type
            contract_item["tenancy_type"] = get_tenancy_type(
                contract_item["tenancy_weeks"])

            # rent_pm
            contract_item["rent_pm"] = float(
                response["room"]["minPriceForBillingCycle"])

            # rent_pw
            contract_item["rent_pw"] = pm_to_pw(contract_item["rent_pm"])

            # rent_total
            contract_item["rent_total"] = contract_item["rent_pm"] * \
                contract_item["tenancy_months"]

            if "universit" in tenancies["tenancyOption"][0]["name"]:
                building_item["description"] = f"{building_item['description']}, noms_in_place"

            # combined_item
            combined_item = CombinedItem()
            combined_item_info = combine_items(
                building_item, room_item, contract_item)
            combined_item.update(combined_item_info)

            yield combined_item
            yield contract_item
            yield building_item

        yield room_item
