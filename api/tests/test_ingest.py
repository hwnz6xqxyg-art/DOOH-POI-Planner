from app.ingest import (SCREEN_FIELDS, auto_detect, build_screen_records,
                        parse_coord, read_spreadsheet)


def test_auto_detect_stroeer():
    headers = ["publisher", "location id", "location name", "latitude", "longitude",
               "city", "postcode", "address/street", "venue type"]
    m = auto_detect(headers, SCREEN_FIELDS)
    assert m["screenId"] == "location id"
    assert m["lat"] == "latitude"
    assert m["lng"] == "longitude"
    assert m["name"] == "location name"
    assert m["city"] == "city"
    assert m["plz"] == "postcode"
    assert m["partnerCol"] == "publisher"


def test_auto_detect_walldecaux():
    headers = ["Environment", "Frame ID", "Latitude", "Longitude", "City DE",
               "Postcode", "Address", "Channel"]
    m = auto_detect(headers, SCREEN_FIELDS)
    assert m["screenId"] == "Frame ID"
    assert m["lat"] == "Latitude"
    assert m["lng"] == "Longitude"
    assert m["city"] == "City DE"
    assert m["plz"] == "Postcode"


def test_parse_coord_eu_comma():
    assert parse_coord("52,5200") == 52.52
    assert parse_coord("13.4050") == 13.405
    assert parse_coord("") is None
    assert parse_coord("n/a") is None


def test_build_screen_records_skips_and_dedupes():
    rows = [
        {"id": "A1", "lat": "52,52", "lng": "13,40", "nm": "Screen A"},
        {"id": "A1", "lat": "52,53", "lng": "13,41", "nm": "Screen A dup"},  # dup -> last wins
        {"id": "", "lat": "1", "lng": "1", "nm": "no id"},                   # skipped
        {"id": "B2", "lat": "", "lng": "", "nm": "no coords"},               # skipped
    ]
    mapping = {"screenId": "id", "lat": "lat", "lng": "lng", "name": "nm"}
    out = build_screen_records(rows, mapping, "TestPartner")
    assert len(out["recs"]) == 1
    assert out["skipped"] == 2
    rec = out["recs"][0]
    assert rec["screen_id"] == "A1"
    assert rec["name"] == "Screen A dup"   # last row wins
    assert rec["lat"] == 52.53


def test_read_csv_semicolon():
    data = "id;lat;lng\nA1;52,52;13,40\n".encode("utf-8")
    parsed = read_spreadsheet(data, "x.csv")
    assert parsed["headers"] == ["id", "lat", "lng"]
    assert len(parsed["rows"]) == 1
    assert parsed["rows"][0]["lat"] == "52,52"
