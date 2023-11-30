# project specific
from utilities import get_country, combine_items, get_tenancy_type, get_room_type, get_currency, pw_to_pm, weeks_to_months
from items import CampusItem, BuildingItem, RoomItem, ContractItem, CombinedItem
from scrapy import Spider, Request
# external packages imports
import pdb
# python packages imports
import json
from datetime import datetime
import logging
logging.debug("This is a warning")


class UniteSpider(Spider):
    name = "unite"
    base_url = 'https://www.unitestudents.com'

    def start_requests(self):
        yield Request(url=self.base_url, callback=self.parse_cities)

    def parse_cities(self, res):

        # loop through cities
        for link in res.css('div[id="CityListBlock"]').css('a'):
            city_url = link.css('::attr(href)').get()
            city = {
                "name": link.css('::text').get(),
                "url":  f"{self.base_url}{city_url}"
            }
            # pdb.set_trace()
            yield Request(url=city["url"], callback=self.parse_properties, meta={"city": city})

    def parse_properties(self, res):
        city_meta = res.meta['city']

        script = [script for script in res.css(
            'script::text').getall() if "ReactDOM" in script][0]
        
        

        start = script.find("CityMapFilterListing, ") + \
            len("CityMapFilterListing, ")
        end = script.find(
            '), document.getElementById("FooterV2')
        
        pdb.set_trace()
        script_json = json.loads(script[start:end])

        # campus item
        for element in script_json["data"]["institution"]:
            campus_item = CampusItem({
                "latitude": float(element["lat"]),
                "longitude": float(element["long"]),
                "institution": element["name"],
                "city": res.meta["city"]["name"]
            })

            # campus name
            campus_name = element["campus"]
            if not campus_name:
                campus_name = element["name"]
            campus_item["name"] = campus_name

            yield campus_item

        for property in script_json["data"]["propertyData"]:

            # facilities
            facilities = [facility["title"]
                          for facility in property["propertyFacilities"]]

            # address
            address_line1 = property["propertyAddress"]["addressLine1"]
            address_line2 = property["propertyAddress"]["addressLine2"]
            city = city_meta["name"]
            postcode = property["propertyAddress"]["postcode"]

            if address_line1:
                address_line1 = address_line1.replace("\r", "")
            if address_line2:
                address_line2 = address_line2.replace("\r", "")
            if postcode:
                postcode = postcode.replace("\r", "")

            if address_line2:
                address = f'{address_line1}, {address_line2}, {postcode} {city}'
            else:
                address = f'{address_line1}, {postcode} {city}'

            building_item = BuildingItem({
                "facilities": facilities,
                "name": property["propertyName"],
                "url": f'{self.base_url}{property["propertyUrl"]}',
                "latitude": property["lat"],
                "longitude": property["long"],
                "address": address,
                "city": city,
                "operator": "Unite Students"
            })

            # country
            building_item["country"] = get_country(
                building_item["latitude"], building_item["longitude"])

            # offers
            offers = "n/a"
            offers_description = property["offerTitle"]
            if offers_description:
                offers = offers_description

            yield Request(url=building_item["url"], callback=self.parse_building, meta={"building_item": building_item, "offers": offers, "building_id": property["propertySerial"]})

    def parse_building(self, res):
        building_item = res.meta["building_item"]
        offers = res.meta["offers"]
        building_id = res.meta["building_id"]

        script = [script for script in res.css(
            'script::text').getall() if "ReactDOM" in script][0]

        start = script.find("PropertyPageFilterListingsMap, ") + \
            len("PropertyPageFilterListingsMap, ")
        end = script.find(
            '), document.getElementById("PropertyPageFilterListingsMap")')
        script_json = json.loads(script[start:end])

        start_header = script.find("PropertyPage.PropertyHeader, ") + \
            len("PropertyPage.PropertyHeader, ")
        end_header = script.find(
            '), document.getElementById("PropertyHeader"))')
        script_header = json.loads(script[start_header:end_header])
        building_item["description"] = script_header["description"].replace(
            '<p>', '').replace('</p>', '').replace('\r\n', '').replace('&rsquo;', "'").replace('&nbsp;', ' ').replace('&amp;', '&').replace("&#39;", "'").replace("&lsquo;", "'").replace('<br /><br />', ' ')

        for property in script_json["propertyData"]["roomData"]:
            if property["propertySerial"] == building_id:
                for room in property["roomTypeAndClasses"]:
                    room_item = RoomItem({
                        "building_name": building_item["name"],
                        "operator": building_item["operator"],
                        "description": room["description"],
                        "url": res.url,
                        # "availability": "available"
                    })

                    # room amenities
                    amenities = [amenity["title"]
                                 for amenity in room["roomFacilities"]]
                    if room["bedSize"]:
                        amenities.append(
                            f'{room["bedSize"]} bed size')
                    if room["roomSize"]:
                        amenities.append(
                            f'{room["roomSize"]} sqm room size')
                    if room["flatMates"]:
                        amenities.append(
                            f'{room["flatMates"]} flatmates')

                    if len(amenities) != 0:
                        room_item["amenities"] = f'{", ".join(amenities)}.'

                    # room name
                    room_item["name"] = f'{room["roomClassName"].title()} - {room["roomType"].title()}'

                    # room availability
                    room_item["availability"] = ("sold out" if len(
                        room["tenancyTypes"]) == 0 else "available")
                    # if len(room["tenancyTypes"]) == 0:
                    #     room_item["availability"] = "sold out"

                    # room type
                    room_item["type"] = get_room_type(room_item["name"])

                    # Room managed by third party: NOMS ?!
                    if len(room["tenancyTypes"]) == 0:

                        # combined_item
                        combined_item = CombinedItem()
                        combined_item_info = combine_items(
                            building_item, room_item)
                        combined_item.update(combined_item_info)

                        yield combined_item

                    # contract item
                    for element in room["tenancyTypes"]:
                        for contract in element["availabilityBands"]:
                            contract_item = ContractItem({
                                "building_name": building_item["name"],
                                "room_name": room_item["name"],
                                "description": contract["bookingType"],
                                "offers": offers,
                                "availability": room_item["availability"]
                            })

                            # academic_year
                            year_n = contract["academicYear"].split('/')[0]
                            year_n1 = contract["academicYear"].split('/')[-1]
                            contract_item["academic_year"] = f'20{year_n}/20{year_n1}'

                            # currency
                            contract_item["currency"] = get_currency(
                                building_item["country"])

                            # contract rent
                            contract_item["rent_pw"] = max(
                                0, float(contract["pricePerWeek"]))
                            contract_item["rent_pm"] = pw_to_pm(
                                contract_item["rent_pw"])
                            contract_item["rent_total"] = max(
                                0, float(contract["totalPrice"]))

                            # tenancy
                            contract_item["tenancy_weeks"] = float(
                                contract["weeks"])
                            if round(contract_item["rent_total"], 2) != round(contract_item["rent_pw"] * contract_item["tenancy_weeks"], 2):
                                contract_item["tenancy_weeks"] = contract["nights"]/7
                            if round(contract_item["rent_total"], 2) != round(contract_item["rent_pw"] * contract_item["tenancy_weeks"], 2):
                                # if the adjustment above is not enough
                                contract_item["tenancy_weeks"] = contract_item["rent_total"] / \
                                    contract_item["rent_pw"]

                            contract_item["tenancy_months"] = weeks_to_months(
                                contract_item["tenancy_weeks"])

                            # set to default if nul
                            if contract_item["rent_pw"] == 0:
                                contract_item["rent_pw"] = "n/a"
                                contract_item["rent_pm"] = "n/a"
                                contract_item["rent_total"] = "n/a"

                            # contract__date_start
                            serial = contract["startBand"]["d"]
                            seconds = serial * 86400
                            contract__date_start = datetime.fromtimestamp(
                                seconds).date()
                            contract_item["date_start"] = contract__date_start

                            # contract__date_end
                            serial = contract["endBand"]["s"]
                            seconds = serial * 86400
                            contract__date_end = datetime.fromtimestamp(
                                seconds).date()
                            contract_item["date_end"] = contract__date_end

                            # contract url
                            contract_item["url"] = (
                                contract["nomsUrl"] if contract["nomsUrl"] else room_item["url"])

                            # tenancy_type
                            contract_item["tenancy_type"] = get_tenancy_type(
                                contract_item["tenancy_weeks"])

                            # combined_item
                            combined_item = CombinedItem()
                            combined_item_info = combine_items(
                                building_item, room_item, contract_item)
                            combined_item.update(combined_item_info)

                            yield contract_item
                            yield combined_item

                    yield room_item

        yield building_item
