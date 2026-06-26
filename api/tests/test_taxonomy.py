from app.taxonomy import classify, extract_brand


def test_branded_retail():
    assert classify({"shop": "chemist", "brand": "Rossmann"}) == ("branded_retail", "chemist")
    assert classify({"shop": "supermarket", "brand": "Edeka"}) == ("branded_retail", "supermarket")
    assert classify({"shop": "electronics"}) == ("branded_retail", "electronics")
    # any branded shop stays discoverable
    assert classify({"shop": "sports", "brand": "Decathlon"}) == ("branded_retail", "other_branded")
    # unbranded, non-listed shop is out of scope
    assert classify({"shop": "kiosk"}) is None


def test_transport_hubs():
    assert classify({"aeroway": "aerodrome", "iata": "MUC"}) == ("transport_hub", "airport")
    assert classify({"railway": "station"}) == ("transport_hub", "rail_station")
    assert classify({"public_transport": "station", "train": "yes"}) == ("transport_hub", "rail_station")
    assert classify({"amenity": "bus_station"}) == ("transport_hub", "bus_station")


def test_leisure_education():
    assert classify({"leisure": "fitness_centre"}) == ("leisure_education", "gym")
    assert classify({"amenity": "university"}) == ("leisure_education", "university")
    assert classify({"amenity": "school"}) == ("leisure_education", "school")
    assert classify({"shop": "mall"}) == ("leisure_education", "mall")
    assert classify({"leisure": "stadium"}) == ("leisure_education", "stadium")


def test_out_of_scope():
    assert classify({"highway": "bus_stop"}) is None
    assert classify({"amenity": "hospital"}) is None  # deferred category
    assert classify({}) is None


def test_brand_extraction():
    assert extract_brand({"brand": "Rossmann", "brand:wikidata": "Q316004"}) == ("Rossmann", "Q316004")
    assert extract_brand({"operator": "Stadtwerke"}) == ("Stadtwerke", None)
    assert extract_brand({}) == (None, None)
