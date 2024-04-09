"""
Function to retrieve sensor data from a remote API.

Log file start and stop time to match to sensors you are retrieving.
13/10/2020: made mkat archive default in function call, allows to override for rts by
using mkat-rts instead of mkat.
"""

import requests


def sensor_data_pvsn(
    sensor,
    timestart,
    timestop,
    sensors_url="http://portal.mkat.karoo.kat.ac.za/katstore/api/query",
):
    """
    Retrieve sensor data from a remote API.

    :param sensor: The name of the sensor to retrieve data for.
    :type sensor: str
    :param timestart: The start time for the data query.
    :type timestart: str (format: 'YYYY-MM-DDTHH:MM:SS')
    :param timestop: The stop time for the data query.
    :type timestop: str (format: 'YYYY-MM-DDTHH:MM:SS')
    :param sensors_url: The URL of the API to query sensor data from. Default is
        'http://portal.mkat.karoo.kat.ac.za/katstore/api/query'.
    :type sensors_url: str
    :return: A tuple containing lists of value timestamps, sample timestamps, and sample
        values.
    :rtype: tuple
    :raises Exception: If the request to the API fails.
    :raises KeyError: If the response does not contain expected keys.
    """
    sample_params = {
        "sensor": sensor,
        "start_time": timestart,
        "end_time": timestop,
        "include_value_time": True,
    }

    # Debug
    # print(sample_params)
    try:
        resp = requests.get(sensors_url, sample_params, timeout=60)
    except requests.exceptions.RequestException as exc:
        print(f"Something failed: {exc}")
    if resp.status_code == 200:
        sample_results = resp.json()
        # Debug
        # print(resp.json())
        timestampv = [sample["value_time"] for sample in sample_results["data"]]
        timestamps = [sample["sample_time"] for sample in sample_results["data"]]
        samples = [sample["value"] for sample in sample_results["data"]]
    else:
        print(f"Request returned with a status code {resp.status_code}")
        print(resp)
    return (timestampv, timestamps, samples)
