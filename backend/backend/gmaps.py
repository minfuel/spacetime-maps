import os
import time
from typing import Iterable

import tqdm.auto as tqdm
import requests

from .location import Location


def get_api_key():
    return os.getenv("GMAPS_API_KEY")


def get_static_map(
    center: Location, zoom: int, markers: list[Location] | None = None
) -> bytes:
    if not 0 <= zoom <= 21:
        raise ValueError("Zoom must be between 0 and 21")

    if markers is None:
        markers = []

    params = {
        "center": center,
        "zoom": zoom,
        "size": "400x400",
        "key": get_api_key(),
        "markers": "|" + "|".join(str(x) for x in markers),
        "scale": 2,
    }
    params_s = "&".join([f"{k}={v}" for k, v in params.items()])
    response = requests.get(
        f"https://maps.googleapis.com/maps/api/staticmap?{params_s}"
    )
    response.raise_for_status()

    return response.content


def call_distance_matrix_api(origins: list[Location], destinations: list[Location]):
    data = {
        "origins": [l.to_route_matrix_location() for l in origins],
        "destinations": [l.to_route_matrix_location() for l in destinations],
        "travelMode": "DRIVE",
        # "travelMode": "TRANSIT",
        # 9:00 UTC is 11:00 CEST
        # "departureTime": "2023-09-04T09:00:00Z",
    }
    for attempt in range(3):
        response = requests.post(
            "https://routes.googleapis.com/distanceMatrix/v2:computeRouteMatrix",
            json=data,
            headers={
                "X-Goog-Api-Key": get_api_key(),
                "X-Goog-FieldMask": "originIndex,destinationIndex,duration,distanceMeters,status,condition",
            },
        )
        if response.status_code == 429:
            print("Rate limit exceeded, retrying...")
            time.sleep(30)
            continue

        response.raise_for_status()
        return response

    raise RuntimeError("Rate limit exceeded")


def get_distance_matrix(
    origins: list[Location], destinations: list[Location]
) -> Iterable[dict]:
    ROOT_MAX_ENTRIES = 25
    MAX_ENTRIES = ROOT_MAX_ENTRIES * 2

    if len(origins) * len(destinations) > MAX_ENTRIES:
        for i in tqdm.trange(0, len(origins), ROOT_MAX_ENTRIES):
            for j in range(0, len(destinations), ROOT_MAX_ENTRIES):
                response = call_distance_matrix_api(
                    origins[i : i + ROOT_MAX_ENTRIES],
                    destinations[j : j + ROOT_MAX_ENTRIES],
                )
                print(response.status_code)
                yield from response.json()
    else:
        response = call_distance_matrix_api(origins, destinations)
        yield from response.json()
