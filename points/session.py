import csv
import json
import requests
import os
import re

from driver import Driver


class Session():
    def __init__(self, config, round_obj, stype, sid="", filename=None):
        self.config = config
        self.round_obj = round_obj
        self.stype = stype
        self.sid = sid
        self.filename = filename
        self.data = []
        self.name_corrections = self.config.get_driver_name_corrections_as_dict(self.round_obj.year)

    def get_type(self):
        return self.stype

    def get_id(self):
        return self.sid

    def get_round(self):
        return self.round_obj

    def get_name(self):
        name = self.stype
        if len(self.sid) > 0:
            name += "-" + self.sid
        return name

    def get_short_name(self):
        if self.stype == "PRACTICE":
            return "P"
        elif self.stype == "QUALIFY":
            return "Q"
        elif self.stype == "HEAT":
            # for heats, we would like to remove all non-numbers (e.g. "heat 1D" -> "H1")
            return "H" + re.sub("[^0-9]", "", self.sid)
        elif self.stype == "MAIN":
            return "M"
        else:
            raise NameError("Unrecognized session type: " + self.stype)

    @staticmethod
    def strip_leading_zeroes(s):
        if s is not None:
            while len(s) > 1 and s[0] == '0' and str(s[1]).isdigit():
                s = s[1:]
        return s

    @staticmethod
    def clean_string(s1=None, s2=None):

        if s1 is not None:
            s1 = str(s1).replace("  ", " ").strip()
            if len(s1) > 0:
                return s1

        if s2 is not None:
            s2 = str(s2).replace("  ", " ").strip()
            if len(s2) > 0:
                return s2

        return None

    @staticmethod
    def is_integer(s):
        try:
            int(s)
            return True
        except ValueError:
            return False

    def is_race(self):
        return self.stype == "MAIN" or self.stype == "HEAT"

    def get_leader(self):
        result = self.data[0]
        if result["pos"] != "1":
            raise LookupError("Leader doesn't have first position: " + str(result))
        return result

    def get_time_difference(self, given_time, leader_time):
        if given_time == "N/A" or leader_time == "N/A":
            return "N/A"
        t1 = self.str_time_to_float(given_time)
        t2 = self.str_time_to_float(leader_time)
        return str(t1 - t2)

    @staticmethod
    def str_time_to_float(str_time):
        # convert strings like "01:04.751" or "59.833" into floating-point number of seconds
        items = str_time.split(":")
        if len(items) == 1:
            return float(items[0])
        elif len(items) == 2:
            return float(items[0]) * 60 + float(items[1])
        else:
            raise LookupError("Invalid time: " + str_time)

    def get_url(self, mylaps_id):
        return self.config.get_mylaps_session_page_url() + str(mylaps_id)

    def download(self, mylaps_id):
        response = requests.get(self.get_url(mylaps_id))
        self.data = json.loads(response.content)

        # determine the directory
        dirname = self.round_obj.get_directory()
        if not os.path.exists(dirname):
            os.makedirs(dirname)

        # store the json
        with open(dirname + "/" + self.get_name() + ".json", "w") as outfile:
            json.dump(self.data, outfile, indent=4)

        # print name of the event
        print "  [x] Downloaded '%s': %s" % (self.get_name(), self.get_url(mylaps_id))

    def read_from_csv(self):

        # determine the directory
        dirname = self.round_obj.get_directory()
        fname = dirname + '/' + self.filename

        # print name of the event
        print "  [x] Reading %s from '%s'" % (self.get_name(), fname)

        # Practice & Qualifier
        #   "Pos" - integer
        #   "No." - kart number
        #   "Name" - driver name (spaces must be be trimmed from both ends)
        #   "Overall BestTm" - best lap (can be empty for last drivers)

        # Heat & Main
        #   "Pos" - integer (but can be DNF or DQ for last drivers)
        #   "No."
        #   "Name"
        #   "Best Tm" - best lap
        #
        #   "In Lap" - lap when best time was set
        #   "Laps" - number of completed laps
        #   "Diff" - time difference from P1 (can be empty for P1 and also for last drivers. can also be DNF or DQ)

        # load the json
        with open(fname, 'rb') as csv_file:
            reader = csv.DictReader(csv_file)
            for row in reader:

                entry = {
                    "pos": self.clean_string(row["Pos"]),
                    "kart": self.clean_string(row["No."]),
                    "driver_name": self.clean_string(row["Name"]),
                    "best_lap_time": self.strip_leading_zeroes(
                        self.clean_string(row.get("Overall BestTm"), row.get("Best Tm")))
                }

                if entry["best_lap_time"] is None:
                    entry["best_lap_time"] = "N/A"

                if self.is_race():
                    entry["best_lap_number"] = self.clean_string(row.get("In Lap"))
                    if entry["best_lap_number"] is None:
                        entry["best_lap_number"] = "N/A"

                    entry["laps_completed"] = self.clean_string(row["Laps"])
                    entry["gap_to_leader"] = self.strip_leading_zeroes(self.clean_string(row["Diff"]))

                    if entry["laps_completed"] is None:
                        entry["laps_completed"] = "0"

                    if entry["gap_to_leader"] is None:
                        entry["gap_to_leader"] = entry["pos"]
                    else:
                        # to workaround differences between "1 Lap" and "1 lap"
                        entry["gap_to_leader"] = entry["gap_to_leader"].upper()

                    # workaround where pos is not set correctly
                    if self.is_not_finished(entry["gap_to_leader"]):
                        entry["pos"] = entry["gap_to_leader"]

                self.data.append(entry)

        # check if positions are in order
        expected_pos = 1
        for entry in self.data:
            # check those who finished
            if self.is_integer(entry["pos"]):
                # can it be out of order?
                if entry["pos"] != str(expected_pos):
                    raise LookupError("Positions are not sorted: " + str(entry) + " vs. " + str(expected_pos))
            expected_pos += 1

        # calculate difference between best laps
        self.recalculate_gaps()

    def read(self):

        # determine the directory
        dirname = self.round_obj.get_directory()
        fname = dirname + '/' + self.filename

        # print name of the event
        print "  [x] Reading %s from '%s'" % (self.get_name(), fname)

        # Practice & Qualifier & Heat & Main
        #   "position" - integer
        #   "start_number" - kart number
        #   "driver" - driver name (spaces must be be trimmed from both ends)
        #   "best_time" - best lap
        #   "best_lap" - lap when best time was set
        #   "laps" - number of completed laps
        #   "diff_time" - time difference from P1 (can be empty for P1 and also for last drivers. can also be DNF or DQ)

        data = json.load(open(fname))
        for row in data["classification"]["rows"]["default"]:
            entry = {
                "pos": self.clean_string(row["position"]),
                "kart": self.clean_string(row["start_number"]),
                "driver_name": self.clean_string(row["driver"]),
                "best_lap_time": self.strip_leading_zeroes(self.clean_string(row.get("best_time")))
            }

            if entry["best_lap_time"] is None:
                entry["best_lap_time"] = "N/A"

            # process driver status and move it to pos
            if row["status"] == "normal":
                # do nothing
                pass
            elif self.is_not_finished(row["status"]):
                # disqualified
                entry["pos"] = row["status"].upper()
            else:
                raise LookupError("Unrecognized driver status in the session: " + row["status"])

            if self.is_race():
                entry["best_lap_number"] = self.clean_string(row.get("best_lap"))
                if entry["best_lap_number"] is None:
                    entry["best_lap_number"] = "N/A"
                entry["laps_completed"] = self.clean_string(row["laps"])
                entry["gap_to_leader"] = self.strip_leading_zeroes(self.clean_string(row["diff_time"]))

                if entry["laps_completed"] is None:
                    entry["laps_completed"] = "0"

                if entry["gap_to_leader"] is None:
                    entry["gap_to_leader"] = entry["pos"]
                else:
                    # to workaround differences between "1 Lap" and "1 lap"
                    entry["gap_to_leader"] = entry["gap_to_leader"].upper()

            self.data.append(entry)

        # check if positions are in order
        expected_pos = 1
        for entry in self.data:
            # check those who finished
            if self.is_integer(entry["pos"]):
                # can it be out of order?
                if entry["pos"] != str(expected_pos):
                    raise LookupError("Positions are not sorted: " + str(entry) + " vs. " + str(expected_pos))
            expected_pos += 1

        # calculate difference between best laps
        self.recalculate_gaps()

    def merge_with(self, another):
        # this is useful for merging the results of mains into one single sheet
        # and then awarding points for the combined/unified race, from top to bottom
        for entry in another.data:
            self.data.append(entry)

    @staticmethod
    def is_not_finished(status):
        status = status.upper()
        return status == 'DQ' or status == 'DNF' or status == 'DNS'

    def remove_not_finished(self):
        # drivers who got disqualified or didn't finish don't have a place assigned, so this method get rids of them
        self.data = [c for c in self.data if self.is_integer(c["pos"])]

    def remove_na_best_time(self):
        # drivers who didn't go on a track don't have best lap time, so this method get rids of them
        self.data = [c for c in self.data if c["best_lap_time"] != "N/A"]

    def move_not_finished_to_end(self):
        # drivers who got disqualified (or didn't finish, or didn't start) don't have a place assigned
        # so this method moves them to the end (useful for mains)
        data_good = []
        data_bad = []
        for entry in self.data:
            if self.is_integer(entry["pos"]):
                data_good.append(entry)
            else:
                data_bad.append(entry)

        self.data = data_good + data_bad

    def remove_duplicate_drivers_advanced_to_mains(self, season_data):
        # drivers who advance from one main to another (e.g. from B-main to A-main) are present in both groups
        # so, when calculating points, these duplicates should be removed
        driver_names = set()
        for entry in self.data:
            driver_name, driver_classes = self.get_driver_name_and_classes(entry["driver_name"], season_data)

            # if driver is already present in the map, the all following occurences should be removed
            if driver_name in driver_names:
                entry["to_be_removed"] = 1
            else:
                driver_names.add(driver_name)

        # remove drivers marked for removal
        self.data = [c for c in self.data if not "to_be_removed" in c]

    def reassign_positions(self):
        position = 1
        for entry in self.data:
            if self.is_integer(entry["pos"]):
                entry["pos"] = str(position)
            position += 1

    def recalculate_gaps(self):
        leader = self.get_leader()
        for entry in self.data:
            entry["best_lap_diff"] = self.get_time_difference(entry["best_lap_time"], leader["best_lap_time"])

    def compare_by_time(self, x, y):
        x_float = self.str_time_to_float(x)
        y_float = self.str_time_to_float(y)

        if x_float < y_float:
            return -1
        elif x_float > y_float:
            return 1
        else:
            return 0

    def sort_by_best_time(self):
        self.data = sorted(self.data, cmp=lambda x, y: self.compare_by_time(x, y), key=lambda x: x['best_lap_time'])

    def get_driver_name_and_classes(self, driver, season_data):
        # capture the part in square brackets "MR", assuming driver name will be something like "John Doe [M][R]"
        # note, that the driver can be on multiple classes: "M" means masters, "R" means rookie, etc.
        driver_class_list = re.findall("\[(.*?)\]", driver)

        # retrieve all driver classes from config
        valid_driver_classes = season_data.get_driver_classes()

        # put all classes into the set
        driver_classes = set("")
        for driver_class in driver_class_list:
            # check if it's a valid driver class
            if not driver_class in valid_driver_classes:
                raise LookupError("Unrecognized driver class: " + driver)
            driver_classes.add(driver_class)

        # this will actually remove the part in brackets
        driver_name = re.sub("\[.*?\]", "", driver)

        # also, remove double spaces and leading/trailing spaces too
        driver_name = driver_name.replace("  ", " ").strip()

        # also, apply corrections from the DB
        if driver_name in self.name_corrections:
            driver_name = self.name_corrections[driver_name]

        # return the tuple
        return driver_name, driver_classes

    def calc_points(self, drivers, season_data):

        if not season_data.is_score_points(self.stype):
            raise LookupError("Points should be awarded, but not found")

        for entry in self.data:
            driver_name, driver_classes = self.get_driver_name_and_classes(entry["driver_name"], season_data)
            position = entry["pos"]

            # add an entry to the dictionary, if it's not there
            driver = Driver(driver_name)
            if not driver in drivers:
                drivers[driver] = driver
            else:
                driver = drivers[driver]

            # add discovered classes to the driver
            driver.add_classes(driver_classes)

            # process points
            if not self.is_integer(entry["pos"]):
                # zero points for DQ or DNF or DNS
                entry["points"] = 0
                driver.set_points(self, 0, entry["pos"])
            else:
                # this is a regular finish
                points = season_data.get_driver_points(self.stype, position)
                entry["points"] = points
                driver.set_points(self, points, "OK")

    def store_points(self, suffix=""):

        # create the directory
        dirname = self.config.get_results_directory() + "/" + str(self.round_obj.year) + \
                  "-round-" + str(self.round_obj.num)
        if not os.path.exists(dirname):
            os.makedirs(dirname)

        # determine the resulting file
        fname = dirname + "/" + self.get_name()
        if suffix:
            fname += "-" + suffix
        fname += ".json"

        # store the table
        print "  [x] Saving results to '%s'" % fname
        with open(fname, "wb") as json_file:
            json.dump(self.data, json_file, indent=4)

    def load_points(self):

        # create the directory
        dirname = self.config.get_results_directory() + "/" + str(self.round_obj.year) + \
                  "-round-" + str(self.round_obj.num)
        if not os.path.exists(dirname):
            os.makedirs(dirname)

        # determine the resulting file
        fname = dirname + "/" + self.get_name() + ".json"

        # store the table
        with open(fname, "rb") as json_file:
            self.data = json.load(json_file)