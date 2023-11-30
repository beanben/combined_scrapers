from scrapy.item import Item, Field

class CampusItem(Item):
    name = Field()
    latitude = Field()
    longitude = Field()
    address = Field()
    city = Field()
    institution = Field()


class BuildingItem(Item):
    address = Field()
    city = Field()
    country = Field()
    description = Field()
    facilities = Field()
    latitude = Field()
    longitude = Field()
    name = Field()
    operator = Field()
    url = Field()
    university_affiliated = Field()

class RoomItem(Item):
    amenities = Field()
    availability = Field()
    building_name = Field()
    description = Field()
    name = Field()
    operator = Field()
    type = Field()
    url = Field()


class ContractItem(Item):
    academic_year = Field()
    availability = Field()
    building_name = Field()
    currency = Field()
    date_end = Field()
    date_start = Field()
    offers = Field()
    rent_pm = Field()
    rent_pw = Field()
    rent_total = Field()
    room_name = Field()
    tenancy_months = Field()
    tenancy_type = Field()
    tenancy_weeks = Field()
    url = Field()
    deposit = Field()
    description = Field()
    utilities_included = Field()
    booking_fee = Field()


class CombinedItem(Item):
    academic_year = Field()
    address = Field()
    contract__availability = Field()
    contract__currency = Field()
    building_description = Field()
    building_name = Field()
    building_url = Field()
    building_university_affiliated = Field()
    city = Field()
    country = Field()
    contract__date_end = Field()
    contract__date_start = Field()
    contract__utilities_included = Field()
    latitude = Field()
    longitude = Field()
    rent_pw = Field()
    rent_pm = Field()
    rent_total = Field()
    room_amenities = Field()
    room_name = Field()
    room_type = Field()
    tenancy_type = Field()
    tenancy_weeks = Field()
    tenancy_months = Field()

    offers = Field()
    operator = Field()


class VenueItem(Item):
    city = Field()
    latitude = Field()
    longitude = Field()
    address = Field()
    name = Field()
    type = Field()