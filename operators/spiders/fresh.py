# project specific
from utilities import get_country, combine_items, get_currency, get_room_type, get_tenancy_type, days_to_weeks, days_to_months, pw_to_pm, weeks_to_months
from items import BuildingItem, RoomItem, ContractItem, CombinedItem
from scrapy import Spider, Request
# external packages imports
import pdb
# python packages imports
import json
from datetime import datetime, date, timedelta
import logging
logging.debug("This is a warning")


class FreshSpider(Spider):
    name = "fresh"
    base_url = 'https://freshstudentliving.co.uk'

    def start_requests(self):
        url = f'{self.base_url}/your-city/'
        yield Request(url=url, callback=self.parse_cities)

    def parse_cities(self, res):
        for element in res.css('div.grid').css('ul').css('li'):
            if 'location' in element.css('a::attr(href)').get():
                city = {
                    "url": element.css('a::attr(href)').get(),
                    "name": element.css('a::text').get()
                }
                yield Request(url=city["url"], callback=self.parse_properties)

    def parse_properties(self, res):
        for element in res.css('ul[id="sortlist"]').css('li'):
            url_scheme = element.css('a::attr(href)').get()
            url_scheme_location = f'{url_scheme}location/'
            yield Request(url=url_scheme_location, callback=self.parse_scheme_location)

    def parse_scheme_location(self, res):
        script = res.css(
            'script[type="application/ld+json"]::text').getall()
        script = json.loads(
            script[-1].replace('\r', '').replace('\n', '').replace('\t', '').replace('5215,', '5215",'))

        # address
        city = script["address"]["addressLocality"]
        postcode = script["address"]["postalCode"]
        street = script["address"]["streetAddress"]

        # coordinates
        coordinates = res.css(
            'input[data-map-directions="gmap"]').css('::attr(data-destination)').get()

        building_item = BuildingItem({
            "name": script["name"].split("From here:")[-1].strip(),
            "address": f'{street}, {postcode} {city}',
            "city": city,
            "latitude": float(coordinates.split(',')[0]),
            "longitude": float(coordinates.split(',')[-1]),
            "operator": "Fresh Student Living"
        })
        # country
        building_item["country"] = get_country(
            building_item["latitude"], building_item["longitude"])

        url_scheme = res.url.split('location/')[0]
        yield Request(url=url_scheme, callback=self.parse_scheme, meta={"building_item": building_item})

    def parse_scheme(self, res):
        building_item = res.meta["building_item"]

        # bulding description
        description = res.css(
            "div.content-read-more__always-visible *::text").getall()
        description = "".join(description).replace(
            '\n', "").replace('\t', "").replace('\r', "").strip()

        building_item.update({
            "description": description,
            "url": res.url,
        })

        url_scheme_offer = f'{res.url}/offers/'
        yield Request(url=url_scheme_offer, callback=self.parse_scheme_offers,  meta={"building_item": building_item})
        yield building_item

    def parse_scheme_offers(self, res):
        building_item = res.meta["building_item"]

        offers = [element.replace("\xa0", "") for element in res.css(
            'div.m-box__content').css('h4 + p::text').getall() if element.replace("\xa0", "")]

        url_rooms = f'{building_item["url"]}rooms'
        yield Request(url=url_rooms, callback=self.parse_rooms,  meta={"building_item": building_item, "offers": offers})

    def parse_rooms(self, res):
        building_item = res.meta["building_item"]
        offers = res.meta["offers"]

        # next academic year
        next_academic_year = res.css(
            'a[data-tab-src="rooms"]').css('::text').get()
        next_academic_year = next_academic_year.split(' ')[-1]
        current_year = int(next_academic_year.split('/')[0])
        next_academic_year = f'{current_year}/{current_year+1}'

        # tenancy start date
        date_start_text = res.css(
            'div[id="property-ajax-box"]').css('p::text').getall()
        index = [i for i, s in enumerate(date_start_text) if 'Tenancy' in s]
        if index:
            index = index[0]
            try:
                date_start = date_start_text[index +
                                             1].replace("Tenancy start date: ", "").strip()
                date_start = datetime.strptime(
                    date_start, '%B %d, %Y').date()
            except ValueError:
                date_start = date_start_text[index].replace(
                    "Tenancy start date: ", "").strip()
                date_start = datetime.strptime(
                    date_start, '%B %d, %Y').date()
        else:
            date_start = date(current_year+1, 9, 1)

        for room in res.css('tbody.room-row-list').css('tr'):
            # room_name
            room_name = room.css(
                'td.align-baseline').css('h4').css('strong::text').get()
            if room_name:

                # room_item
                room_item = RoomItem({
                    "building_name": building_item["name"],
                    "operator": building_item["operator"],
                    "url": res.url,
                    "name": room_name.lower()
                })

                # room availability
                availability = room.css(
                    'div.m-box__content--pad-third').css('span::text').get()
                room_item["availability"] = (
                    "sold out" if availability == "Sold out" else "available")

                # room type
                room_item["type"] = get_room_type(room_item["name"])

                # room description
                room_item["description"] = room.css(
                    'td.align-baseline').css('p::text').get()

                # rent
                rent = room.css('td.nop').css('dd.strong::text').getall()
                rent = [el.replace("£", "").replace("€", "").strip()
                        for el in rent]
                rent = [el for el in rent if el]

                if len(rent) == 1:
                    update_possible = True
                    rent = rent[0]
                else:
                    rents = rent
                    update_possible = False

                if update_possible:

                    # contract
                    contract_item = ContractItem({
                        "building_name": building_item["name"],
                        "room_name": room_item["name"],
                        "academic_year": next_academic_year,
                        "date_start": date_start,
                        "offers": offers,
                        "url": res.url,
                        "availability": room_item["availability"],
                    })

                    # tenancy
                    tenancy = room.css('td.nop').css('dt.light::text').get()
                    tenancy = tenancy.replace("\t", "").replace("\n", "")
                    if tenancy.lower() == "flexible":
                        contract_item["tenancy_weeks"] = 51
                    else:
                        contract_item["tenancy_weeks"] = int(
                            tenancy.replace("weeks", ""))
                    contract_item["tenancy_months"] = weeks_to_months(
                        contract_item["tenancy_weeks"])

                    # rent_pw
                    contract_item["rent_pw"] = float(rent.replace("*", ""))

                    # rent_pm
                    contract_item["rent_pm"] = pw_to_pm(
                        contract_item["rent_pw"])

                    # currency
                    contract_item["currency"] = get_currency(
                        building_item["country"])

                    # end date
                    contract_item["date_end"] = contract_item["date_start"] + \
                        timedelta(7*contract_item["tenancy_weeks"])

                    # rent_total
                    contract_item["rent_total"] = contract_item["tenancy_weeks"] * \
                        contract_item["rent_pw"]

                    # tenancy_type
                    contract_item["tenancy_type"] = get_tenancy_type(
                        contract_item["tenancy_weeks"])

                    # CombinedItem
                    combined_item = CombinedItem()
                    combined_item_info = combine_items(
                        building_item, room_item, contract_item)
                    combined_item.update(combined_item_info)

                    yield combined_item
                    yield contract_item
                    yield room_item

                if not update_possible and rents:
                    # tenancies
                    tenancies = room.css('td.nop').css(
                        'dt.light::text').getall()
                    try:
                        tenancies = [int(el.replace("weeks", ""))
                                     for el in tenancies]
                        yield Request(url=res.url, callback=self.parse_other_rooms, dont_filter=True, meta={
                            "building_item": building_item,
                            "offers": offers,
                            "room_item": room_item,
                            "next_academic_year": next_academic_year,
                            "rents": rents,
                            "tenancies": tenancies
                        })
                    except:
                        room_names = tenancies
                        room_names = [el.replace("\t", "").replace(
                            "\n", "") for el in room_names]

                        yield Request(url=res.url, callback=self.parse_other_rooms, dont_filter=True, meta={
                            "building_item": building_item,
                            "offers": offers,
                            "room_item": room_item,
                            "next_academic_year": next_academic_year,
                            "rents": rents,
                            "room_names": room_names
                        })

            # for current academic year
            url_short_term = f'{building_item["url"]}short-term-lets/'
            yield Request(url=url_short_term, callback=self.parse_st_rooms, meta={"building_item": building_item, "current_year": current_year, "offers": offers}, dont_filter=True)

    def parse_other_rooms(self, res):
        building_item = res.meta["building_item"]
        offers = res.meta["offers"]
        room_item = res.meta["room_item"]
        next_academic_year = res.meta["next_academic_year"]
        rents = res.meta["rents"]
        tenancies = res.meta.get("tenancies")
        room_names = res.meta.get("room_names")

        # info from initial room_item
        room_name = room_item["name"]
        room_availability = room_item["availability"]
        room_description = room_item["description"]

        # room_item and contract item
        for k in range(len(rents)):
            # room item
            room_item = RoomItem({
                "building_name": building_item["name"],
                "operator": building_item["operator"],
                "description": room_description,
                "availability": room_availability,
                "url": res.url
            })
            # room_name
            room_item["name"] = (room_names[k] if room_names else room_name)
            # if room_names:
            #     room_item["name"] = room_names[k]
            # else:
            #     room_item["name"] = room_name

            # room type
            room_item["type"] = get_room_type(room_item["name"])

            if tenancies:

                # tenancy
                tenancy_weeks = tenancies[k]
                tenancy_months = weeks_to_months(tenancy_weeks)

                # date_start
                date_start = res.css(
                    'div.l-container').css('div.grid__cell').css('p *::text').getall()
                date_start = "".join(date_start)
                start = date_start.find("Tenancy start date:") + \
                    len("Tenancy start date:")
                end = date_start.find("Check out")
                if "Flexible" in date_start:
                    end = date_start.find("Flexible")
                date_start = date_start[start:end].strip()
                date_start = datetime.strptime(date_start.strip(), '%B %d, %Y')
                date_start = date_start.date()

                # date_end
                date_end = date_start + timedelta(7 * tenancy_weeks)

            else:
                # date_start
                start = room_description.find("from ") + len("from ")
                date_start = room_description[start:].split(
                    "-")[0].replace("th", "")
                date_start = datetime.strptime(
                    date_start.strip(), '%d %B %Y')
                date_start = date_start.date()

                # date_end
                date_end = room_description[start:].split(
                    "-")[-1].replace("th", "").replace(".", "")
                date_end = datetime.strptime(date_end.strip(), '%d %B %Y')
                date_end = date_end.date()

                # tenancy
                tenancy_weeks = days_to_weeks(date_start, date_end)
                tenancy_months = days_to_months(date_start, date_end)

            # contract_item
            contract_item = ContractItem({
                "building_name": building_item["name"],
                "room_name": room_item["name"],
                "academic_year": next_academic_year,
                "rent_pw": float(rents[k].replace("*", "")),
                "rent_pm": pw_to_pm(float(rents[k].replace("*", ""))),
                "tenancy_weeks": tenancy_weeks,
                "tenancy_months": tenancy_months,
                "date_end": date_end,
                "date_start": date_start,
                "offers": offers,
                "url": res.url,
                "availability": room_item["availability"],
            })

            # currency
            contract_item["currency"] = get_currency(
                building_item["country"])

            # rent_total
            contract_item["rent_total"] = contract_item["tenancy_weeks"] * \
                contract_item["rent_pw"]

            # tenancy_type
            contract_item["tenancy_type"] = get_tenancy_type(
                contract_item["tenancy_weeks"])

            # combined_item
            combined_item = CombinedItem()
            combined_item_info = combine_items(
                building_item, room_item, contract_item)
            combined_item.update(combined_item_info)

            yield combined_item
            yield contract_item
            yield room_item

    def parse_st_rooms(self, res):
        building_item = res.meta["building_item"]
        current_year = res.meta["current_year"]
        offers = res.meta["offers"]
        current_academic_year = f'{current_year-1}/{current_year}'

        # dates
        today = date.today()
        date_start = date(current_year, today.month + 1, 1)
        date_end = date(current_year, 9, 1)

        # tenancy
        tenancy_weeks = days_to_weeks(date_start, date_end)
        tenancy_months = days_to_months(date_start, date_end)

        for room in res.css('div[id="engine-quarter"]').css('tbody.room-row-list').css('tr'):
            # room name
            room_name = room.css(
                'td.align-baseline').css('h4').css('strong::text').get()

            if room_name:
                room_item = RoomItem({
                    "building_name": building_item["name"],
                    "operator": building_item["operator"],
                    "description": room.css('td.align-baseline').css('p::text').get(),
                    "name": room.css('td.align-baseline').css('h4').css('strong::text').get(),
                    "url": res.url,
                    # "availability": "available"
                })

                # room availability
                room_availability = room.css(
                    'div.m-box__content--pad-third').css('span::text').get()
                room_item["availability"] = (
                    "sold out" if room_availability == "Sold out" else "available")
                # if room_availability == "Sold out":
                #     room_item["availability"] = "sold out"

                # room type
                room_item["type"] = get_room_type(room_item['name'])

                # contract_item
                contract_item = ContractItem({
                    "building_name": building_item["name"],
                    "room_name": room_item["name"],
                    "academic_year": current_academic_year,
                    "tenancy_weeks": tenancy_weeks,
                    "tenancy_months": tenancy_months,
                    "date_start": date_start,
                    "date_end": date_end,
                    "offers": offers,
                    # "tenancy_type": "longer tenancy",
                    "url": res.url,
                    "availability": room_item["availability"],
                })

                # currency
                contract_item["currency"] = get_currency(
                    building_item["country"])

                # rent
                rent = room.css('td.nop').css('dd.strong::text').get()
                rent = rent.replace("£", "").replace("€", "")
                if rent:
                    contract_item.update({
                        "rent_pw": float(rent),
                        "rent_pm": pw_to_pm(float(rent)),
                        "rent_total": float(rent) * contract_item["tenancy_weeks"]
                    })

                # tenancy_type
                contract_item["tenancy_type"] = get_tenancy_type(
                    contract_item["tenancy_weeks"])

                # combined_item
                combined_item = CombinedItem()
                combined_item_info = combine_items(
                    building_item, room_item, contract_item)
                combined_item.update(combined_item_info)

                yield combined_item
                yield contract_item
                yield room_item
