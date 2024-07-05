"""Old code kept for reference. NOT USABLE AS IS."""

import logging
import time

logger = logging.getLogger("sculib")


class SCU:
    """System Control Unit."""

    # Direct SCU webapi functions based on urllib PUT/GET
    def feedback(self, r):
        """
        This function logs feedback information and returns.

        This function logs the request URL, request body, reason, status code, text
        returned if debug mode is enabled or if the status code is not 200.

        :param r: The response object.
        :type r: Response object
        """
        logger.error("Not implemented because this function is not needed.")
        return
        # if self.debug == True:
        #     logger.info("***Feedback:", r.request.url, r.request.body)
        #     logger.info(r.reason, r.status_code)
        #     logger.info("***Text returned:")
        #     logger.info(r.text)
        # elif r.status_code != 200:
        #     logger.info("***Feedback:", r.request.url, r.request.body)
        #     logger.info(r.reason, r.status_code)
        #     logger.info("***Text returned:")
        #     logger.info(r.text)
        #     # logger.info(r.reason, r.status_code)
        #     # logger.info()

    def acu_ska_track_stoploadingtable(self):
        """
        Stop loading table track.

        This function is not implemented because the function "stopLoadingTable" is not
        supported by the OPC UA server.
        """
        logger.error(
            "Not implemented because the function "
            '"stopLoadingTable" is not supported by the OPC UA '
            "server."
        )
        return
        # self.scu_put('/acuska/stopLoadingTable')

    # 	def scu_get(device, params = {}, r_ip = self.ip, r_port = port):
    def scu_get(self, device, params={}):
        """
        Perform a GET request to a specified device on the SCU.

        :param device: The device to send the GET request to.
        :type device: str
        :param params: Parameters to include in the GET request (default is an empty
            dictionary).
        :type params: dict
        :return: The response from the GET request.
        :rtype: requests.Response object
        """
        logger.error("Not implemented because this function is not needed.")
        return
        # """This is a generic GET command into http: scu port + folder
        # with params=payload"""
        # URL = "http://" + self.ip + ":" + self.port + device
        # r = requests.get(url=URL, params=params)
        # self.feedback(r)
        # return r

    def scu_put(self, device, payload={}, params={}, data=""):
        """
        Perform a PUT request to a specific device on the SCU.

        :param device: The device endpoint to send the PUT request.
        :type device: str
        :param payload: The JSON data to send in the PUT request.
        :type payload: dict
        :param params: The parameters to include in the PUT request.
        :type params: dict
        :param data: Additional data to include in the PUT request.
        :type data: str
        :return: Response object from the PUT request.
        :rtype: requests.Response
        """
        logger.error("Not implemented because this function is not needed.")
        return
        # """This is a generic PUT command into http: scu port + folder
        # with json=payload"""
        # URL = "http://" + self.ip + ":" + self.port + device
        # r = requests.put(url=URL, json=payload, params=params, data=data)
        # self.feedback(r)
        # return r

    def scu_delete(self, device, payload={}, params={}):
        """
        Send a DELETE request to a specific device.

        :param device: The device to send the DELETE request to.
        :type device: str
        :param payload: The payload data to send in the request.
        :type payload: dict
        :param params: The parameters to include in the request.
        :type params: dict
        :return: The response object from the DELETE request.
        :rtype: requests.models.Response
        """
        logger.error("Not implemented because this function is not needed.")
        return
        # """This is a generic DELETE command into http: scu port + folder
        # with params=payload"""
        # URL = "http://" + self.ip + ":" + self.port + device
        # r = requests.delete(url=URL, json=payload, params=params)
        # self.feedback(r)
        # return r

    # SIMPLE PUTS

    def command_authority(self, action: bool = None, username: str = ""):
        """
        Check and execute a command based on the specified action and username.

        :param action: A boolean value representing the action to be performed.
        :type action: bool
        :param username: The username of the user requesting the action.
        :type username: str
        :return: The result of the command execution.
        :rtype: result type
        :raises KeyError: If the action provided is not valid.
        """
        # TODO: authority not defined!
        # if action not in authority:
        #   logger.error("command_authority requires the action to be Get or Release!")
        #   return
        if len(username) <= 0:
            logger.error(
                "command_authority command requires a user as second parameter!"
            )
            return
        # 1 get #2 release
        logger.info("command authority: ", action)
        authority = {"Get": True, "Release": False}
        return self.commands["CommandArbiter.TakeReleaseAuth"](
            authority[action], username
        )

    # status get functions goes here

    def status_Value(self, sensor):  # noqa: N802
        """
        Get the value of a specific sensor from the attributes dictionary.

        :param self: The object instance.
        :param sensor: The key identifying the specific sensor.
        :type sensor: str
        :return: The value of the specified sensor.
        :rtype: any
        """
        return self.attributes[sensor].value

    def status_finalValue(self, sensor):  # noqa: N802
        """
        Return the final value status of a sensor.

        :param sensor: The sensor for which to get the final value status.
        :type sensor: str
        """
        logger.error(
            "Not implemented because the function "
            '"finalValue" is not supported by the OPC UA '
            "server."
        )
        return
        # return self.status_Value(sensor)
        # r = self.scu_get('/devices/statusValue',
        #       {'path': sensor})
        # data = r.json()['finalValue']
        # logger.info('finalValue: ', data)
        # return data

    def commandMessageFields(self, commandPath):  # noqa: N802,N803
        """
        Generate message fields for a specific command path.

        :param commandPath: The specific path for the command.
        :type commandPath: str
        """
        logger.error(
            "Not implemented because the function "
            '"commandMessageFields" is not supported by the OPC UA '
            "server."
        )
        return
        # r = self.scu_get('/devices/commandMessageFields',
        #       {'path': commandPath})
        # return r

    def statusMessageField(self, statusPath):  # noqa: N802,N803
        """
        Retrieve the status message field.

        :param statusPath: The path to the status message field.
        :type statusPath: str
        """
        logger.error(
            "Not implemented because the function "
            '"statusMessageFields" is not supported by the OPC UA '
            "server."
        )
        return
        # r = self.scu_get('/devices/statusMessageFields',
        #       {'deviceName': statusPath})
        # return r

    # ppak added 1/10/2020 as debug for onsite SCU version
    # but only info about sensor, value itself is murky?
    def field(self, sensor):
        """
        Return data for a specific sensor field.

        :param sensor: The name of the sensor field to retrieve data for.
        :type sensor: str
        :return: Data for the specified sensor field.
        :rtype: dict
        """
        logger.error(
            'Not implemented because the function "field" is not '
            "supported by the OPC UA server."
        )
        return
        # old field method still used on site
        r = self.scu_get("/devices/field", {"path": sensor})
        # data = r.json()['value']
        data = r.json()
        return data

    # logger functions goes here

    def create_logger(self, config_name, sensor_list):
        """
        PUT create a config for logging.

        Usage:
        create_logger('HN_INDEX_TEST', hn_feed_indexer_sensors)
        or
        create_logger('HN_TILT_TEST', hn_tilt_sensors)
        """
        logger.info("create logger")
        r = self.scu_put(
            "/datalogging/config", {"name": config_name, "paths": sensor_list}
        )
        return r

    """unusual does not take json but params"""

    def start_logger(self, filename):
        """
        Start logging data to a specified file.

        :param filename: The name of the file to log data to.
        :type filename: str
        :return: Response from the server.
        :rtype: str
        """
        logger.info("start logger: ", filename)
        r = self.scu_put("/datalogging/start", params="configName=" + filename)
        return r

    def stop_logger(self):
        """
        Stop the data logging process.

        :return: The response from stopping the data logging.
        :rtype: Depends on the response from the SCU.
        """
        logger.info("stop logger")
        r = self.scu_put("/datalogging/stop")
        return r

    def logger_state(self):
        #        logger.info('logger state ')
        """
        Get the current state of the logger.

        :return: The current state of the logger.
        :rtype: str
        """
        r = self.scu_get("/datalogging/currentState")
        # logger.info(r.json()['state'])
        return r.json()["state"]

    def logger_configs(self):
        """
        Get logger configurations.

        :return: The logger configurations.
        :rtype: dict
        """
        logger.info("logger configs ")
        r = self.scu_get("/datalogging/configs")
        return r

    def last_session(self):
        """GET last session."""
        logger.info("Last sessions ")
        r = self.scu_get("/datalogging/lastSession")
        session = r.json()["uuid"]
        return session

    def logger_sessions(self):
        """GET all sessions."""
        logger.info("logger sessions ")
        r = self.scu_get("/datalogging/sessions")
        return r

    def session_query(self, uid):
        """
        GET specific session only - specified by uid number.

        Usage:
            session_query('16')
        """
        logger.info("logger sessioN query uid ")
        r = self.scu_get("/datalogging/session", {"uid": uid})
        return r

    def session_delete(self, uid):
        """
        DELETE specific session only - specified by uid number.

        Not working - returns response 500
        Usage:
        session_delete('16')
        """
        logger.info("delete session ")
        r = self.scu_delete("/datalogging/session", params="uid=" + uid)
        return r

    def session_rename(self, uid, new_name):
        """
        RENAME specific session only - specified by uid number and new session name.

        Not working
        Works in browser display only, reverts when browser refreshed!
        Usage:
        session_rename('16','koos')
        """
        logger.info("rename session ")
        r = self.scu_put("/datalogging/session", params={"uid": uid, "name": new_name})
        return r

    def export_session(self, uid, interval_ms=1000):
        """
        EXPORT specific session.

        By uid and with interval output r.text could be directed to be saved to file.

        Usage:
        export_session('16',1000)
        or export_session('16',1000).text
        """
        logger.info("export session ")
        r = self.scu_get(
            "/datalogging/exportSession",
            params={"uid": uid, "interval_ms": interval_ms},
        )
        return r

    # sorted_sessions not working yet

    def sorted_sessions(
        self,
        is_descending="True",
        start_value="1",
        end_value="25",
        sort_by="Name",
        filter_type="indexSpan",
    ):
        """
        Retrieve a sorted list of sessions from the data logging endpoint.

        :param is_descending: Flag to specify whether the sorting should be descending
            or ascending. Default is descending.
        :type is_descending: str
        :param start_value: Starting value for the sorting range. Default is 1.
        :type start_value: str
        :param end_value: Ending value for the sorting range. Default is 25.
        :type end_value: str
        :param sort_by: Field to sort by. Default is 'Name'.
        :type sort_by: str
        :param filter_type: Type of filtering to apply. Default is 'indexSpan'.
        :type filter_type: str
        :return: A sorted list of sessions based on the specified parameters.
        :rtype: dict
        """
        logger.info("sorted sessions")
        r = self.scu_get(
            "/datalogging/sortedSessions",
            {
                "isDescending": is_descending,
                "startValue": start_value,
                "endValue": end_value,
                "filterType": filter_type,  # STRING - indexSpan|timeSpan,
                "sortBy": sort_by,
            },
        )
        return r

    # get latest session
    def save_session(self, filename, interval_ms=1000, session="last"):
        """
        Save session data as CSV after EXPORTing it.

        Default interval is 1s. Default is last recorded session if specified no error
        checking to see if it exists.

        Usage:
            export_session('16',1000)
            or export_session('16',1000).text
        """
        from pathlib import Path

        logger.info(
            "Attempt export and save of session: %s at rate %d ms", session, interval_ms
        )
        if session == "last":
            # get all logger sessions, may be many
            # r = self.logger_sessions()
            # [-1] for end of list, and ['uuid'] to get uid of last session in list
            session = self.last_session()
        file_txt = self.export_session(session, interval_ms).text
        logger.info("Session id: %s", session)
        file_time = str(int(time.time()))
        file_name = str(filename + "_" + file_time + ".csv")
        file_path = Path.cwd() / "output" / file_name
        logger.info("Log file location:", file_path)
        f = open(file_path, "a+")
        f.write(file_txt)
        f.close()

    # get latest session ADDED BY HENK FOR BETTER FILE NAMING FOR THE OPTICAL TESTS
    # (USING "START" AS TIMESTAMP)
    def save_session13(self, filename, start, interval_ms=1000, session="last"):
        """
        Save session data as CSV after EXPORTing it.

        Default interval is 1s. Default is last recorded session if specified no error
        checking to see if it exists.

        Usage:
            export_session('16',1000)
            or export_session('16',1000).text
        """
        from pathlib import Path

        logger.info(
            "Attempt export and save of session: %s at rate %d ms", session, interval_ms
        )
        if session == "last":
            # get all logger sessions, may be many
            # r = self.logger_sessions()
            # [-1] for end of list, and ['uuid'] to get uid of last session in list
            session = self.last_session()
        file_txt = self.export_session(session, interval_ms).text
        logger.info("Session id: %s", session)
        #        file_time = str(int(time.time()))
        file_time = str(int(start))
        file_name = str(filename + "_" + file_time + ".csv")
        file_path = Path.cwd() / "output" / file_name
        logger.info("Log file location:", file_path)
        f = open(file_path, "a+")
        f.write(file_txt)
        f.close()

    def save_session14(self, filename, interval_ms=1000, session="last"):
        """
        Save session data as CSV after EXPORTing it.

        Default interval is 1s. Default is last recorded session if specified no error
        checking to see if it exists.

        Usage:
            export_session('16',1000)
            or export_session('16',1000).text
        """
        from pathlib import Path

        logger.info(
            "Attempt export and save of session: %s at rate %d ms", session, interval_ms
        )
        if session == "last":
            # get all logger sessions, may be many
            # r = self.logger_sessions()
            session = self.last_session()
        file_txt = self.export_session(session, interval_ms).text
        logger.info("Session id: %s", session)
        file_name = str(filename + ".csv")
        file_path = Path.cwd() / "output" / file_name
        logger.info("Log file location:", file_path)
        f = open(file_path, "a+")
        f.write(file_txt)
        f.close()

    # Simplified one line commands particular to test section being peformed

    # wait seconds, wait value, wait finalValue
    def wait_duration(self, seconds):
        """
        Wait for a specified duration in seconds.

        :param seconds: The duration to wait in seconds.
        :type seconds: float
        """
        logger.info(f"  wait for {seconds:.1f}s", end="")
        time.sleep(seconds)
        logger.info(" done *")

    def wait_value(self, sensor, value):
        """
        Wait until a sensor reaches a specific value.

        :param sensor: The sensor to monitor.
        :type sensor: str
        :param value: The value to wait for.
        :type value: int
        """
        logger.info(f"wait until sensor: {sensor} == value {value}")
        while self.attributes[sensor].value != value:
            time.sleep(1)
        logger.info(f" {sensor} done *")

    def wait_finalValue(self, sensor, value):  # noqa: N802
        """
        Wait until the sensor reaches a specified value.

        :param sensor: The sensor to monitor.
        :type sensor: str
        :param value: The target value for the sensor.
        :type value: int
        :raises: If the sensor does not reach the target value within a reasonable time.
        """
        logger.info(f"wait until sensor: {sensor} == value {value}")
        while self.status_finalValue(sensor) != value:
            time.sleep(1)
        logger.info(f" {sensor} done *")
