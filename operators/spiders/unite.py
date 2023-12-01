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
            yield Request(url=city["url"], callback=self.parse_properties, meta={"city": city})

    def parse_properties(self, res):
        city_meta = res.meta['city']
        script_json_str = self.extract_script(res)
        if not script_json_str:
            return

        try:
            script_json = json.loads(script_json_str)
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON parsing error: {e}")
            return

        # for element in script_json["institution"]:
        #     yield self.create_campus_item(element, city_meta)

        for building in script_json["uniteProperties"]:
             yield Request(
                 url = f'{self.base_url}{building["propertyPageUrl"]}',
                 callback=self.parse_building,
                 meta = {
                    "building_item": self.create_building_item(building, city_meta),
                    "offers": building.get("offerTitle", "n/a"),
                    "building_id": building["propertySerial"]
                 }
             )

    def extract_script(self, response):
        try:
            script = next(script for script in response.css(
                'script::text').getall() if "ReactDOM" in script)
            start_marker = 'CityPageManager, '
            end_marker = ',"gtmCid":"GTM-THBRD"'
            start = script.find(start_marker) + len(start_marker)
            end = script.find(end_marker)
            if start == -1 or end == -1:
                raise ValueError("Start or end marker not found in script")
            return script[start:end] + '}'
        except (IndexError, ValueError) as e:
            self.logger.error(f"Script extraction error: {e}")
            return None

    # def create_campus_item(self, element, city_meta):
    #     campus_name = element.get("campus", element["name"])
    #     return CampusItem({
    #         "latitude": float(element["lat"]),
    #         "longitude": float(element["long"]),
    #         "institution": element["name"],
    #         "city": city_meta["name"],
    #         "name": campus_name,
    #         "country": get_country(float(element["lat"]), float(element["long"])),
            
    #     })
    
    def create_building_item(self, building, city_meta):
        # pdb.set_trace()
        return BuildingItem({
            "facilities": [facility["title"] for facility in building["facilities"]],
            "name": building["name"],
            "url": f'{self.base_url}{building["propertyPageUrl"]}',
            "latitude": building["lat"],
            "longitude": building["long"],
            "address": self.format_address(building["address"]),
            "postcode": building["address"]["postcode"].replace("\r", ""),
            "city": city_meta["name"],
            "operator": "Unite Students"
        })

    def format_address(self, address_data):
        address_line1 = address_data["addressLine1"].replace("\r", "")
        address_line2 = address_data.get("addressLine2","").replace("\r", "")
        return f'{address_line1}, {address_line2}' if address_line2 else f'{address_line1}'

    # COTINUE HERE 
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
