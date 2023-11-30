# project specific
from utilities import get_country, combine_items, get_currency, get_room_type, get_tenancy_type, get_city, get_address, pw_to_pm, weeks_to_months, weeks_to_months
from items import CampusItem, BuildingItem, RoomItem, ContractItem, CombinedItem, VenueItem
from scrapy import Spider, Request
from scrapy.http import TextResponse
# external packages imports
import pdb
import requests
from urllib import parse
# python packages imports
from datetime import datetime, timedelta
import json
import re
import logging
logging.debug("This is a warning")


def date_formating(date_text):
    months_abv = {
        "Sept": "Sep",
        "June": "Jun"
    }
    date_elements = date_text.split(" ")
    day = date_elements[0]
    month = date_elements[1]
    year = date_elements[-1]
    if month in months_abv.keys():
        month = months_abv[month]

    return f'{day} {month} {year}'


class HostSpider(Spider):
    name = "host"
    base_url = 'https://host-students.com/'
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

    other_urls = ['http://lacemarketstudios.co.uk/',
                  'http://onepenrhynroad.london/',
                  'http://the-hive.london/',
                  'http://the-hub.london/']

    uni_urls = {
        "https://www.anglia.ac.uk": "Anglia Ruskin University",
        "https://www1.uwe.ac.uk": "University of the West of England Bristol",
        "http://www.bristol.ac.uk": "University of Bristol",
        "https://www.cumbria.ac.uk": "University of Cumbria"
    }

    # CONTINUE THERE
    different_urls = ['http://www.victoriahallkingscross.com/',
                      'https://www.pointcampus.ie/']

    def start_requests(self):
        yield Request(url=self.base_url, callback=self.parse_cities, headers=self.headers)

    def parse_cities(self, res):
        for bullet in res.css('ul.checkerboard__list').css('li'):
            city = {
                "name": bullet.css('h2::text').get(),
                "url": bullet.css('a::attr(href)').get()
            }

            yield Request(url=city["url"], callback=self.parse_properties, meta={"city": city}, headers=self.headers, dont_filter=True)

    def parse_properties(self, res):
        city = res.meta['city']

        for property in res.css('ul.property-list__list').css('li.property-list__item'):

            # contract offers:
            offers = property.css(
                'ul.building-offers__list').css('li.building-offers__list-item::text').getall()
            offers = [element.replace("\n", "").strip() for element in offers]
            if len(offers) == 0:
                offers = "n/a"

            # building address
            address = property.css('address').css('p::text').getall()
            address = [element.replace("\n", "").strip() for element in address]
            address = " ,".join(
                [element for element in address if element][:-1])

            # building item
            building_item = BuildingItem({
                "name": property.css('h2').css('a::text').get().replace("\n", "").strip()[:-1],
                "city": city["name"],
                "address": address,
                "url": property.css('h2').css('a::attr(href)').get(),
                "operator": "Host Students"
            })

            # noms uni
            uni_url_key = [
                url for url in self.uni_urls if url in building_item["url"]]

            if uni_url_key:
                noms_uni = self.uni_urls[uni_url_key[0]]
                building_item.update({
                    "description": f'Nomination agreement in place with the university: {noms_uni}. Rents and tenancies can be found on the universities website: {uni_url_key[0]}',
                    "university_affiliated": noms_uni
                })

                # combined_item
                combined_item = CombinedItem()
                combined_item_info = combine_items(building_item)
                combined_item.update(combined_item_info)

                yield combined_item
                yield building_item

            elif self.base_url in building_item["url"]:
                yield Request(url=building_item["url"], callback=self.parse_host_property, meta={"building_item": building_item, "offers": offers}, headers=self.headers, dont_filter=True)

            elif building_item["url"] in self.other_urls:
                yield Request(url=building_item["url"], callback=self.parse_other_property, meta={"building_item": building_item, "offers": offers}, headers=self.headers, dont_filter=True)

            elif building_item["url"] in self.different_urls:
                if "victoriahallkingscross" in building_item["url"]:
                    yield Request(url=f'{building_item["url"]}location/', callback=self.parse_victoriahall, meta={"building_item": building_item}, headers=self.headers, dont_filter=True)

                elif "pointcampus.ie" in building_item["url"]:
                    yield Request(url=building_item["url"], callback=self.parse_pointcampus, meta={"building_item": building_item}, headers=self.headers, dont_filter=True)

            else:
                # combined_item
                combined_item = CombinedItem()
                combined_item_info = combine_items(building_item)
                combined_item.update(combined_item_info)
                yield combined_item
                yield building_item

    def parse_host_property(self, res):
        building_item = res.meta['building_item']
        offers = res.meta['offers']

        # facilities
        facilities = res.css(
            'div.split-feature__content').css('ul').css('li.separated-list__item::text').getall()
        facilities = [element.replace("\n", "").strip()
                      for element in facilities]
        facilities = [element for element in facilities if element]

        # coordinates
        coordinates = res.css('section[id="map"]').css('div.map__map')
        lat = coordinates.css('::attr(data-centre)').get().split(',')[0]
        lng = coordinates.css('::attr(data-centre)').get().split(',')[1]

        building_item.update({
            "description": res.css('div.billboard__main').css('p::text').get(),
            "facilities": facilities,
            "latitude": float(lat),
            "longitude": float(lng)
        })

        # building description
        description = res.css('div.billboard__main').css('p::text').get()
        if not description:
            description = res.css('div.billboard__main').css(
                'span:not([class="h3"])::text').get()
            description = description .replace("\xa0", "")
        building_item["description"] = description

        # country
        building_item["country"] = get_country(
            building_item["latitude"], building_item["longitude"])

        # campus
        campus_names = res.css('h3.transport-list__heading *::text').getall()
        # campus coordinates
        campus_details = res.css('section[id="map"]').css(
            '::attr(data-markers)').get()
        campus_details = json.loads(campus_details)
        for campus in campus_details["unis"]:
            campus_item = CampusItem({
                "name": campus["title"],
                "latitude": float(campus["lat"]),
                "longitude": float(campus["lng"]),
                "address": campus["address"],
                "institution": campus["title"].split("-")[0].strip()
            })

        for room in res.css('ul.room-list__list').css('li.room-list__item'):

            room_item = RoomItem({
                "building_name": building_item["name"],
                "operator": building_item["operator"],
                "name": room.css('h3.listed-room__title::text').get(),
                "url": room.css('a::attr(href)').get(),
            })

            # availability
            room_availability = room.css(
                'strong.listed-room__avail::text').getall()[-1].strip().lower()
            room_item["availability"] = (
                'sold out' if room_availability == "sold out" else 'available')

            yield Request(url=room_item["url"], callback=self.parse_host_room, meta={"room_item": room_item, "building_item": building_item, "offers": offers}, dont_filter=True, headers=self.headers)

        yield building_item

    def parse_host_room(self, res):
        room_item = res.meta["room_item"]
        building_item = res.meta["building_item"]
        offers = res.meta["offers"]

        description = list()
        titles = res.css(
            'div.room-details-container').css('h3.h4::text').getall()
        contents = res.css('div.room-details-container').css('ul')

        # room description
        details = list()
        for element in contents[0].css('li'):
            key = element.css(
                'strong.room-detail-item__label::text').get()
            value = element.css(
                'span.room-detail-item__value::text').get()
            details.append({key: value})

        room_item["description"] = details

        # room amenities
        details = list()
        for element in contents[1].css('li'):
            # key = element.css(
            #     'strong.room-detail-item__label::text').get()
            amenity = element.css(
                'span.room-detail-item__value::text').get()
            details.append(amenity)

        room_item["amenities"] = f'{", ".join(details)}.'

        # room type
        room_item["type"] = get_room_type(room_item['name'])

        # contract_item
        for contract in res.css('select[id="contract-length-select"]').css('option[data-selected-id]'):

            contract_item = ContractItem({
                "building_name": building_item["name"],
                "room_name": room_item['name'],
                "offers": offers,
                "availability": room_item["availability"]
            })

            # currency
            contract_item["currency"] = get_currency(
                building_item["country"])

            # rent_pw
            rent_pw = contract.css(
                '::attr("data-dynamic-price")').get()
            end = rent_pw.find(" pw")
            try:
                rent_pw = float(rent_pw[1:end])
            except:
                rent_pw = res.css(
                    'select[id="contract-length-select"]').css('option::attr(data-dynamic-price)').get()
                end = rent_pw.find(" pw")
                rent_pw = float(rent_pw[1:end])

            contract_item.update({
                "rent_pw": rent_pw,
                "rent_pm": pw_to_pm(rent_pw)
            })

            # tenancy_weeks
            timing_details = contract.css('::text').get()
            if "flexible" in timing_details.lower():
                # date start
                date_start = datetime.now()

                # date end
                start = timing_details.find(
                    "Contract ends ") + len("Contract ends ")
                date_end = timing_details[start:].replace(")", "").replace(
                    "th", "").replace("nd", "").replace("rd", "")
                date_end = datetime.strptime(date_end, "%d %B %Y")

                # tenancy weeks
                tenancy_days = (date_end - date_start).days
                tenancy_weeks = int(round(int(tenancy_days)/7, 0))
            else:
                # date end
                date_end = timing_details.split("-")
                if len(date_end) == 1:
                    date_end = timing_details.split("–")
                date_end = date_end[-1]
                date_end = date_end.replace(
                    "th", "").replace("2nd", "2").replace("3rd", "3").replace("1st", "1").replace(")", "").strip()
                try:
                    date_end = datetime.strptime(date_end, "%d %B %Y")
                except:
                    date_end = contract.css(
                        'option::attr("data-dynamic-price")').get().split("-")[-1]
                    date_end = date_end.replace(
                        "th", "").replace("2nd", "2").replace("3rd", "3").replace("1st", "1").replace("pw", "").replace(".", "").strip()
                    date_end = datetime.strptime(date_end, "%d %B %Y")

                # tenancy weeks
                tenancy_weeks = [element for element in timing_details.split(
                    "-") if "weeks" in element][0]
                end = tenancy_weeks.find(" weeks")
                try:
                    tenancy_weeks = int(tenancy_weeks[:end])
                except:
                    tenancy_weeks = int(timing_details.split("-")[1])

                # date start
                date_start = [element for element in timing_details.split(
                    "-") if "(" in element][0]
                start = date_start.find("(") + len("(")
                date_start = date_start[start:].strip().replace(
                    "th", "").replace("2nd", "2").replace("3rd", "3").replace("1st", "1").strip()
                try:
                    date_start = datetime.strptime(date_start, "%d %B %Y")
                except:
                    date_start = date_end - timedelta(days=7 * tenancy_weeks)

            contract_item.update({
                "date_start": date_start.date(),
                "date_end": date_end.date(),
                "tenancy_weeks": tenancy_weeks,
                "url": res.url
            })

            # academic year
            academic_year = contract.css(
                '::text').get().split('-')[0].strip()
            if len(academic_year.split("/")[-1]) == 2:
                academic_year = f'{academic_year.split("/")[0]}/20{academic_year.split("/")[-1]}'
            contract_item["academic_year"] = academic_year

            end = contract_item["academic_year"].find("Flexible")
            if end != -1:
                contract_item["academic_year"] = contract_item["academic_year"][:end].strip(
                )
            if "/" not in contract_item["academic_year"]:
                year_end = contract_item["date_end"].year
                contract_item["academic_year"] = f'{year_end-1}/{year_end}'

            # rent total
            contract_item["rent_total"] = contract_item["rent_pw"] * \
                contract_item["tenancy_weeks"]

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

    def parse_other_property(self, res):
        building_item = res.meta['building_item']
        offers = res.meta['offers']

        # building description
        if "the-hive.london" in building_item["url"]:

            building_item["description"] = res.css('div.et_pb_row_inner_0').css(
                'div.et_pb_text_inner').css('span::text').get()
        else:
            description = res.css('div.et_pb_row_inner_0').css(
                'div.et_pb_text_inner')
            description_title = description.css('h3::text').get()
            description_text = description.css(
                'p::text').get()
            if description_title:
                building_item["description"] = f'{description_title} {description_text}'
            else:
                building_item["description"] = description_text

        # facilities
        if "the-hive.london" in building_item["url"]:
            facilities = res.css('div.et_pb_text_1').css(
                'div.et_pb_text_inner').css('strong::text').getall()
            building_item["facilities"] = "".join(
                [facilities[0], facilities[1]])

        else:
            building_item["facilities"] = res.css('div.et_pb_row_inner_1').css(
                'h4').css('span::text').getall()

        # url location
        url_location = res.css(
            'div.header-content').css('a::attr(href)').getall()
        url_location = [url for url in url_location if "location" in url][0]
        yield Request(url=url_location, callback=self.parse_location, meta={"building_item": building_item, "offers": offers}, dont_filter=True)

    def parse_location(self, res):
        building_item = res.meta['building_item']
        offers = res.meta['offers']

        # location
        script_locations = res.css(
            'div.et_pb_code_inner').css('script::text').get()

        start = script_locations.find(
            '$("#map1").maps(') + len('$("#map1").maps(')
        end = script_locations.find(').data("wpgmp_maps")')
        script_locations = script_locations[start:end].replace("\\", "")

        # remove content in script
        pattern = ',"infowindow_setting"(.*?)">Read More...</a></div>"}'
        remove = re.search(pattern, script_locations).group(1)
        remove = f',"infowindow_setting"{remove}">Read More...</a></div>"}}'
        script_locations = script_locations.replace(remove, "")
        script_locations = script_locations.replace(
            ',"filters":{"filters_container":"[data-container="wpgmp-filters-container"]"}', '')
        script_locations = script_locations.replace(
            '"constantly inventive"', "'constantly inventive'")
        script_locations = json.loads(script_locations)

        # get coordindates of building & details of venues
        for venue in script_locations["places"]:
            venue_type = venue["categories"][0]["name"].lower()

            # coordindates of building
            if building_item["name"].lower() in venue_type:
                building_item.update({
                    "latitude": float(venue["location"]["lat"]),
                    "longitude": float(venue["location"]["lng"]),
                })
                # country
                building_item["country"] = get_country(
                    building_item["latitude"], building_item["longitude"])

            # campus_item
            elif venue_type == "university" or venue_type == "universities":
                campus_item = CampusItem({
                    "name": venue["title"],
                    "latitude": float(venue["location"]["lat"]),
                    "longitude": float(venue["location"]["lng"])
                })
                campus_item.update({
                    "institution": campus_item["name"],
                    "city": get_city(
                        campus_item["latitude"], campus_item["longitude"]),
                    "address": get_address(campus_item["latitude"], campus_item["longitude"])
                })
                yield campus_item

            # venue_item
            else:
                venue_item = VenueItem({
                    "name": venue["title"],
                    "latitude": float(venue["location"]["lat"]),
                    "longitude": float(venue["location"]["lng"]),
                    "type": venue_type
                })
                venue_item.update({
                    "city": get_city(
                        venue_item["latitude"], venue_item["longitude"]),
                    "address": get_address(venue_item["latitude"], venue_item["longitude"])
                })

                yield venue_item

        # room_url
        room_url = res.css('li.menu-item').css('a::attr(href)').getall()
        room_url = [url for url in room_url if "room" in url][0]
        yield Request(url=room_url, callback=self.parse_other_host_room, meta={"building_item": building_item}, dont_filter=True, headers=self.headers)

    def parse_other_host_room(self, res):
        building_item = res.meta["building_item"]

        # additional building description
        try:
            addtl_description = res.css('div.et_pb_text_0').css(
                'p').css('span::text').getall()[1]
        except:
            addtl_description = res.css(
                'div.et_pb_text_0').css('p::text').getall()[-2]
        building_item["description"] = f'{building_item["description"]} {addtl_description}'

        # offer
        offers_url = res.css('div.et_pb_section_0').css(
            'a::attr(href)').getall()
        offers_url = [url for url in offers_url if "offer" in url]
        offers_dict = dict()
        if offers_url:
            offers_url = offers_url[0]
            request = requests.get(offers_url)
            resp = TextResponse(body=request.content, url=offers_url)

            offers = resp.css(
                'div.generic-content-page__inner').css('h3 *::text').getall()
            offers = [el.replace("\xa0", "").replace(
                ":", "").strip() for el in offers]
            indices_bookings = [i for i, el in enumerate(
                offers) if 'Bookings' in el]

            if len(indices_bookings) == 1:
                academic_year = offers[indices_bookings[0]].split(" ")[0]
                academic_year = f'{academic_year.split("/")[0]}/20{academic_year.split("/")[-1]}'

                # offer 1
                offers_dict[academic_year] = " ".join(
                    offers[indices_bookings[0]+1:])

            elif len(indices_bookings) == 2:
                indices_offers = [i for i, el in enumerate(
                    offers) if 'OFFERS' in el]

                # offer 1
                academic_year_1 = offers[indices_offers[0]].split(" ")[0]
                academic_year_1 = f'{academic_year_1.split("/")[0]}/20{academic_year_1.split("/")[-1]}'
                offers_dict[academic_year_1] = ", ".join(
                    offers[indices_offers[0]+1:indices_offers[1]])

                # offer 2
                academic_year_2 = offers[indices_offers[1]].split(" ")[0]
                academic_year_2 = f'{academic_year_2.split("/")[0]}/20{academic_year_2.split("/")[-1]}'
                offers_dict[academic_year_2] = ", ".join(
                    offers[indices_offers[1]+1:])

        # room items
        for room in res.css('li.room-list'):
            room_item = RoomItem({
                "building_name": building_item["name"],
                "operator": building_item["operator"],
                "name": room.css('h3::text').get(),
                "availability": "available",
                "url": room.css('a.view-room-button::attr(href)').get()
            })
            # availability
            availability = room.css('p.room-status::text').get()
            if availability.lower() == "sold out":
                room_item["availability"] = "sold out"

            # room type
            room_item["type"] = get_room_type(room_item["name"])

            # room amenities_1
            amenities_1 = res.css('div.et_pb_column_1_6').css(
                'h4').css('span::text').getall()
            if not amenities_1:
                amenities_1 = res.css('div.et_pb_column_1_6').css(
                    'h5').css('span::text').getall()
            if amenities_1:
                amenities_1 = [am.strip() for am in amenities_1]
                room_item["amenities"] = amenities_1

            yield Request(url=room_item["url"], callback=self.parse_other_host_room_detail, meta={"building_item": building_item, "room_item": room_item, "offers_dict": offers_dict, "amenities_1": amenities_1}, dont_filter=True, headers=self.headers)

        yield building_item

    def parse_other_host_room_detail(self, res):
        building_item = res.meta["building_item"]
        room_item = res.meta["room_item"]
        offers_dict = res.meta["offers_dict"]
        amenities_1 = res.meta["amenities_1"]

        # description
        room_item["description"] = res.css('p *::text').getall()[1]

        # room amenities_2
        amenities_2 = res.css('h4.et_pb_module_header').css(
            'span::text').getall()
        if amenities_1 and amenities_2:
            amenities_1.extend(amenities_2)
            room_item["amenities"] = amenities_1
        elif amenities_2:
            room_item["amenities"] = amenities_2

        # contracts
        if "the-hive.london" in res.url:
            contracts = res.css('div.et_pb_section_4').css(
                'div.et_pb_code_inner').css('p').getall()
        else:
            contracts = res.css('div.et_pb_text_1').css(
                'div.et_pb_text_inner').css('p').getall()

        # contract_items
        for contract in contracts:
            contract_item = ContractItem({
                "availability": room_item["availability"],
                "building_name": building_item["name"],
                "currency": get_currency(building_item["country"]),
                "room_name": room_item["name"],
                "url": res.url
            })

            # academic_year
            academic_years = contract.split(" – ")[0].replace("<p>", "")
            academic_year_1 = academic_years.split("/")[0]
            academic_year_2 = academic_years.split("/")[-1].split(" ")[0]
            contract_item["academic_year"] = f'{academic_year_1}/20{academic_year_2}'

            # dates
            dates = contract.split(" – ")[-1]
            start = dates.find("From ") + len("From ")
            end = dates.find(" to")
            date_start = dates[start:end]
            date_end = dates[end+len(" to"):].replace("</p>", "").strip()
            contract_item.update({
                "date_start": datetime.strptime(
                    date_start, '%d/%m/%y').date(),
                "date_end": datetime.strptime(
                    date_end, '%d/%m/%y').date()
            })

            # offers
            contract_item["offers"] = offers_dict[contract_item["academic_year"]]

            # tenancy
            tenancy = contract.split(" – ")[1].replace("weeks", "").strip()
            contract_item.update({
                "tenancy_weeks": int(tenancy),
                "tenancy_months": weeks_to_months(int(tenancy)),
                "tenancy_type": get_tenancy_type(int(tenancy))
            })

            # rents
            rent_pw = contract.split(" – ")[-1].split("<br>")[0]
            rent_pw = int(rent_pw.replace("£", "").replace("pw", ""))
            contract_item.update({
                "rent_pw": rent_pw,
                "rent_pm": pw_to_pm(rent_pw),
                "rent_total": rent_pw * contract_item["tenancy_weeks"]
            })

            # combined_item
            combined_item = CombinedItem()
            combined_item_info = combine_items(
                building_item, room_item, contract_item)
            combined_item.update(combined_item_info)
            yield combined_item
            yield contract_item

        yield room_item

    def parse_victoriahall(self, res):
        building_item = res.meta["building_item"]

        # coordinates
        coordinates = res.css('div.cms_position_main').css(
            'a.text_links_link::attr(href)').get()
        pattern = "/@(.*?),17z/"
        coordinates = re.search(pattern, coordinates).group(1)
        building_item.update({
            "latitude": float(coordinates.split(",")[0]),
            "longitude": float(coordinates.split(",")[1]),
        })

        # building country
        building_item["country"] = get_country(
            building_item["latitude"], building_item["longitude"])

        # building description
        url_description = res.url.replace("location", "about")
        request = requests.get(url_description)
        resp = TextResponse(body=request.content, url=url_description)
        description = resp.css('div.textarea_right').css(
            'div.textarea_text *::text').getall()
        description = [el.replace("\xa0", "").strip()
                       for el in description if el]
        building_item["description"] = "".join(description)

        # building facilities
        url_facilities = res.url.replace("location", "facilities")
        request = requests.get(url_facilities)
        resp = TextResponse(body=request.content, url=url_facilities)
        features_1 = resp.css('div.features_col_left').css(
            'div.features_element_heading::text').getall()
        features_2 = resp.css('div.features_col_right').css(
            'div.features_element_heading::text').getall()
        features_1.extend(features_2)
        building_item["facilities"] = features_1

        # rooms
        url_rooms = res.url.replace("location", "rooms")
        yield Request(url=url_rooms, callback=self.parse_victoriahall_rooms, meta={"building_item": building_item}, dont_filter=True, headers=self.headers)
        yield building_item

    def parse_victoriahall_rooms(self, res):
        building_item = res.meta["building_item"]

        # room description
        description_title = res.css('div.textarea_heading::text').get()
        description_text = res.css('div.textarea_text::text').get()
        room_description = f'{description_title}. {description_text}'

        # loop through rooms
        for room in res.css('div.specifications_area').css('div.specifications_room'):
            room_item = RoomItem({
                "building_name": building_item["name"],
                "operator": building_item["operator"],
                "url": res.url,
                "description": room_description,
            })
            # room name
            header = room.css('div.specifications_room_heading::text').get()
            room_item["name"] = header.split(" – ")[0]

            # room availability
            room_item["availability"] = (
                'available' if 'available' in header else 'sold out')

            # academic_year
            academic_year = header.split(" ")[-1].strip()
            if academic_year.lower() == "out":
                academic_year = "n/a"
            else:
                academic_year = f'{academic_year.split("/")[0]}/20{academic_year.split("/")[-1]}'

            # room amenities
            amenities = []
            pattern = '<(.*?)>'
            for el in room.css('div.specifications_room_feature').getall():
                remove = re.search(pattern, el).group(1)
                el = el.replace(remove, "")
                el = el.replace("<>", "").replace("\r", "").replace(
                    "\t", "").replace("\n", "").strip()
                el = el.replace("</div>", "").replace("<br>", " ")
                amenities.append(el)

            contracts = [el for el in amenities if "weeks" in el]

            amenities = [el for el in amenities if el not in contracts]
            room_item["amenities"] = ". ".join(amenities)

            # room type
            room_item["type"] = get_room_type(room_item["name"])

            # contract items
            for contract in contracts:
                contract_item = ContractItem({
                    "availability": room_item["availability"],
                    "building_name": building_item["name"],
                    "room_name": room_item["name"],
                    "url": res.url,
                    "utilities_included": " ".join(el for el in amenities if "included" in el)
                })

                # academic_year
                if "/" in contract:
                    academic_year = contract.split(" ")[0]
                    academic_year = f'{academic_year.split("/")[0]}/20{academic_year.split("/")[-1]}'
                if academic_year == "n/a" and "(" in contract:
                    years = contract.split("(")[-1]
                    years = years.split(" - ")
                    year_1 = years[0].split(" ")[-1]
                    year_2 = years[-1].split(" ")[-1].replace(")", "")
                    academic_year = f'{year_1}/{year_2}'

                contract_item["academic_year"] = academic_year

                # currency
                contract_item["currency"] = get_currency(
                    building_item["country"])

                # date_end
                date_end = contract.split(" - ")[-1].replace(")", "").replace(
                    "th", "").replace("rd", "").replace("st", "").replace("nd", "").strip()
                date_end = date_formating(date_end)
                contract_item["date_end"] = datetime.strptime(
                    date_end, "%d %b %Y").date()

                # date_start
                date_start = contract.split("(")[-1]
                date_start = date_start.split(" - ")[0].replace(
                    "th", "").replace("rd", "").replace("st", "").replace("nd", "").strip()
                date_start = date_formating(date_start)
                contract_item["date_start"] = datetime.strptime(
                    date_start, "%d %b %Y").date()

                # rent_pw
                rent_pw = contract.split(" ")
                rent_pw = [el.replace("pw", "").replace("£", "").strip()
                           for el in rent_pw if "pw" in el]
                rent_pw = float(rent_pw[0])
                contract_item.update({
                    "rent_pw": rent_pw,
                    "rent_pm": pw_to_pm(rent_pw)
                })

                # tenancy_weeks
                tenancy_weeks = contract.split(" - ")
                tenancy_weeks = [el.replace("weeks", "").strip()
                                 for el in tenancy_weeks if "weeks" in el]
                tenancy_weeks = int(tenancy_weeks[0])
                contract_item.update({
                    "tenancy_weeks": tenancy_weeks,
                    "tenancy_months": weeks_to_months(tenancy_weeks),
                    "tenancy_type": get_tenancy_type(tenancy_weeks)
                })

                # combined_item
                combined_item = CombinedItem()
                combined_item_info = combine_items(
                    building_item, room_item, contract_item)
                combined_item.update(combined_item_info)

                yield combined_item
                yield room_item
                yield contract_item

    def parse_pointcampus(self, res):
        building_item = res.meta["building_item"]

        # building description
        description = res.css('div.pointcampus-text').css('p::text').getall()
        building_item["description"] = " ".join(description)

        # building coordinates
        url_location = 'https://pointcampus.ie/wp-content/themes/point-campus-2021/json/locations_block_6013e08e439b7.json'
        request = requests.get(url_location)
        resp = TextResponse(body=request.content, url=url_location)

        education_institutions = ["school", "university", "college"]

        for venue in resp.json():
            if venue["title"].lower() == building_item["name"].lower():
                building_item.update({
                    "latitude": float(venue["latitude"]),
                    "longitude": float(venue["longitude"])
                })
            elif any(el in education_institutions for el in venue["title"].lower()):
                campus_item = CampusItem({
                    "name": venue["title"],
                    "latitude": float(venue["latitude"]),
                    "longitude": float(venue["longitude"]),
                    "institution": venue["title"]
                })

                # address & city
                campus_item.update({
                    "address": get_address(campus_item["latitude"], campus_item["longitude"]),
                    "city": get_city(campus_item["latitude"], campus_item["longitude"])
                })
                yield campus_item

        # building country
        building_item["country"] = get_country(
            building_item["latitude"], building_item["longitude"])

        # building facilities
        url_facilities = f'{res.url}student-facilities/'
        request = requests.get(url_facilities)
        resp = TextResponse(body=request.content, url=url_facilities)
        facilities = resp.css(
            'div.point-campus-feature-title::text').getall()
        facilities = [el.replace(
            "\r", "").replace("\n", "").strip() for el in facilities]
        building_item["facilities"] = ", ".join(facilities)

        # rooms
        for rooms in res.css('ul.sub-menu').css('li.menu-item-object-pointcampus_rooms'):
            url_rooms = rooms.css('a::attr(href)').get()
            yield Request(url=url_rooms, callback=self.parse_pointcampus_rooms, meta={"building_item": building_item}, dont_filter=True, headers=self.headers)

        yield building_item

    def parse_pointcampus_rooms(self, res):
        building_item = res.meta["building_item"]

        # amenities
        room_amenities = res.css('p.room-details-text::text').getall()
        room_amenities = [el.strip()
                          for el in room_amenities if "size" not in el.lower()]
        room_amenities = ", ".join(room_amenities)

        # room description
        description = res.css(
            'div.single-room-description').css('p::text').getall()
        description = [el.strip() for el in description]
        description = "".join(description)

        for room in res.css('table.single-room-tabs-room-types-table').css('tbody').css('tr'):
            room_item = RoomItem({
                "availability": "available",
                "building_name": building_item["name"],
                "description": description,
                "name": room.css('td.main-details::text').get(),
                "operator": building_item["operator"],
                "url": res.url
            })

            # room amenities:
            room_size = room.css('td.size').css(
                'span.right-details::text').get()
            room_item["amenities"] = f'{room_amenities}, room is {room_size}'

            # room type
            room_item["type"] = get_room_type(room_item["name"])

            # dates
            url_dates = room.css('td.booknow').css('a::attr(href)').get()
            request = requests.get(url_dates)
            resp = TextResponse(body=request.content, url=url_dates)
            dates = dict()
            for el in resp.css('div.selection-panel'):
                title = el.css('span.title::text').get()
                tenancy_weeks = title.split(" ")[0]
                academic_year = title.split(" ")[-1].replace("-", "/")
                tenancy_timings = el.css('span.markdown').css('p::text').get()
                tenancy_start = tenancy_timings.split(
                    "-")[0].replace("(", "").strip()
                tenancy_start = datetime.strptime(
                    tenancy_start, "%d/%m/%Y").date()
                tenancy_end = tenancy_timings.split(
                    "-")[-1].replace(")", "").strip()
                tenancy_end = datetime.strptime(tenancy_end, "%d/%m/%Y").date()
                dates[tenancy_weeks] = {
                    "date_start": tenancy_start,
                    "date_end": tenancy_end,
                    "academic_year": academic_year
                }

            # offers
            url_offers = f'{res.url}offers/'
            request = requests.get(url_offers)
            resp = TextResponse(body=request.content, url=url_offers)
            offers = resp.css(
                'div.point-campus-offer-title').css('h2::text').getall()
            offers = f'{", ".join(offers)}.'

            # contract utilities_included
            utilities_included = res.css(
                'div.single-room-amenities').css('span::text').getall()
            utilities_included = [
                el for el in utilities_included if "bills" in el.lower() or "free " in el.lower()]
            utilities_included = f'{", ".join(utilities_included)}.'

            # contract_item
            contracts = room.css('td').getall()
            contracts = [el for el in contracts if "wks" in el]

            # contract_available flag
            contract_available = True

            for el in contracts:
                el = el.replace('<span class="left-details">', '')
                el = el.replace('<span class="right-details">', '')
                el = el.replace('</span>', '')
                el = el.replace('<td>', '')
                el = el.replace('</td>', '')

                tenancy_weeks = el.split("wks")[0]
                rent_pw = el.split("wks")[-1].replace("€", "")
                if rent_pw == "NA":
                    contract_available = False
                else:
                    contract_item = ContractItem({
                        "academic_year": dates[tenancy_weeks]["academic_year"],
                        "availability": "available",
                        "building_name": building_item["name"],
                        "currency": get_currency(building_item["country"]),
                        "date_end": dates[tenancy_weeks]["date_end"],
                        "date_start": dates[tenancy_weeks]["date_start"],
                        "offers": offers,
                        "rent_pw": int(rent_pw),
                        "rent_pm": pw_to_pm(int(rent_pw)),
                        "rent_total": int(tenancy_weeks) * int(rent_pw),
                        "room_name": room_item["name"],
                        "tenancy_months": weeks_to_months(int(tenancy_weeks)),
                        "tenancy_type": get_tenancy_type(int(tenancy_weeks)),
                        "tenancy_weeks": int(tenancy_weeks),
                        "url": res.url,
                        "utilities_included": utilities_included
                    })

                    # combined_item
                    combined_item = CombinedItem()
                    combined_item_info = combine_items(
                        building_item, room_item, contract_item)
                    combined_item.update(combined_item_info)
                    yield combined_item
                    yield contract_item

            yield room_item
