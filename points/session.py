import json
import requests
import os
import re
from tinydb import where
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
        self.point_adjustments = self.load_point_adjustments()
        self.already_applied_point_adjustments = False

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

    @staticmethod
    def parse_name_into_stype_sid(name):
        result = name.split("-")
        stype = result[0]
        sid = ""
        if len(result) > 1:
            sid = result[1]
        return stype, sid

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

            # process driver status and copy it to pos too
            entry["status"] = row["status"].upper()
            if entry["status"] == 'NORMAL':
                # change it to a shorter version
                entry["status"] = 'OK'
            elif not self.is_not_regular_finish(entry["status"]):
                # if not DQ, DNF, or DNS, then raise exception
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

        # reassign all positions
        self.reassign_positions()

        # calculate difference between best laps
        self.recalculate_best_lap_gaps()

    def merge_with(self, another):
        # this is useful for merging the results of mains into one single sheet
        # and then awarding points for the combined/unified race, from top to bottom
        for entry in another.data:
            self.data.append(entry)

    @staticmethod
    def is_not_regular_finish(status):
        return status == 'DQ' or status == 'DNF' or status == 'DNS'

    def remove_not_finished(self):
        # drivers who got disqualified, or didn't finish, or didn't start will be removed
        # useful for merging the qualifiers together and keeping only drivers with valid best laps
        self.data = [c for c in self.data if c["status"] == 'OK']

    def remove_na_best_time(self):
        # drivers who didn't go on a track don't have best lap time, so this method get rids of them
        self.data = [c for c in self.data if c["best_lap_time"] != "N/A"]

    def remove_duplicate_drivers_advanced_to_mains(self, season_data):
        # drivers who advance from one main to another (e.g. from B-main to A-main) are present in both groups
        # so, when calculating points, these duplicates should be removed
        driver_names = {}
        for entry in self.data:
            driver_name, driver_classes = self.get_driver_name_and_classes(entry["driver_name"], season_data)

            # if driver is already present in the map, the all following occurrences should be removed
            if driver_name in driver_names:
                # let's see which one needs to be removed
                entry_higher = driver_names[driver_name]

                # if driver finished in the higher entry, then the lower one needs to be removed
                # otherwise, we need to remove the higher one (e.g. A-main = DQ, B-main = points)
                if entry_higher["status"] == 'OK':
                    entry["to_be_removed"] = 1
                else:
                    entry_higher["to_be_removed"] = 1
            else:
                driver_names[driver_name] = entry

        # remove drivers marked for removal
        self.data = [c for c in self.data if not "to_be_removed" in c]

    def reassign_positions(self):
        position = 1
        for entry in self.data:
            entry["pos"] = str(position)
            position += 1

    def recalculate_best_lap_gaps(self):
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

    def get_driver_name_and_classes(self, driver, season_data=None):
        # capture the part in square brackets "MR", assuming driver name will be something like "John Doe [M][R]"
        # note, that the driver can be on multiple classes: "M" means masters, "R" means rookie, etc.
        driver_class_list = re.findall("\[(.*?)\]", driver)

        # put all classes into the set
        driver_classes = set("")
        for driver_class in driver_class_list:
            # check if it's a valid driver class
            if (season_data is not None) and (driver_class not in season_data.get_driver_classes()):
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

    def lookup_driver_row_idx(self, driver_name):
        # find driver
        idx = -1
        for i in xrange(len(self.data)):
            entry = self.data[i]
            if entry["driver_name_canonical"] == driver_name:
                idx = i
                break

        return idx

    def apply_adjustment_move_driver(self, driver_name, is_move_up):
        idx = self.lookup_driver_row_idx(driver_name)

        # if not found, return right away
        if idx < 0:
            return False

        # swap drivers (up)
        if is_move_up and idx - 1 >= 0:
            t = self.data[idx]
            self.data[idx] = self.data[idx - 1]
            self.data[idx - 1] = t
            return True

        # swap drivers (down)
        if not is_move_up and idx + 1 < len(self.data):
            t = self.data[idx]
            self.data[idx] = self.data[idx + 1]
            self.data[idx + 1] = t
            return True

        return False

    def apply_adjustment_assign_points_to_driver(self, driver_name, points):
        idx = self.lookup_driver_row_idx(driver_name)

        # if not found, return right away
        if idx < 0:
            return False

        self.data[idx]["points"] = points
        return True

    def apply_point_adjustments(self):
        if self.already_applied_point_adjustments:
            return

        # iterate through stored adjustments
        count_applied = 0
        for driver_name, adjustment_list in self.point_adjustments.iteritems():
            for adjustment in adjustment_list:

                # for position-based adjustments
                if adjustment['type'] == 'adjust_position':
                    positions = adjustment['positions']
                    for i in xrange(abs(positions)):
                        if not self.apply_adjustment_move_driver(driver_name, positions <= 0):
                            break

                # for point-based adjustments
                if adjustment['type'] == 'adjust_points':
                    points = adjustment['points']
                    self.apply_adjustment_assign_points_to_driver(driver_name, points)

                count_applied += 1

        # if something was applied, we need to reassign positions
        if count_applied > 0:
            self.reassign_positions()

        self.already_applied_point_adjustments = True

    def calc_points(self, drivers, season_data):

        if not season_data.is_score_points(self.stype):
            raise LookupError("Points should be awarded, but can't find them in season configuration")

        # add an entry to the dictionary, if it's not there
        for entry in self.data:
            driver_name, driver_classes = self.get_driver_name_and_classes(entry["driver_name"], season_data)

            # determine and store canonical name
            entry["driver_name_canonical"] = driver_name

            # add an entry to the dictionary, if it's not there
            driver = Driver(driver_name)
            if not driver in drivers:
                drivers[driver] = driver
            else:
                driver = drivers[driver]

            # add discovered classes to the driver
            driver.add_classes(driver_classes)

        # apply all stored point adjustments
        self.apply_point_adjustments()

        # process the actual points
        for entry in self.data:

            # look up driver
            driver = drivers[Driver(entry["driver_name_canonical"])]

            # determine driver position
            position = entry["pos"]

            # if points were overwritten as a part of post-race adjustments, then assign this exact value
            if "points" in entry:
                driver.set_points(self, entry["points"], entry["status"])
                continue

            # assign points based on the status & position
            if entry["status"] == 'OK':
                # this is a regular finish
                points = season_data.get_driver_points(self.stype, position)
                entry["points"] = points
                driver.set_points(self, points, entry["status"])

            elif entry["status"] == 'DNS':
                # DNS is 'did not start'
                # person gets 0 points always. he stays on the rankings, but it creates a gap in points
                entry["points"] = 0
                driver.set_points(self, 0, entry["status"])

            elif entry["status"] == 'DNF':
                # DNF is 'did not finish'
                # we just assign points in order in this case
                # i.e. someone who crashed on lap 5 gets less points vs. someone who crashed on lap 6
                points = season_data.get_driver_points(self.stype, position)
                entry["points"] = points
                driver.set_points(self, points, entry["status"])

            elif entry["status"] == 'DQ':
                # DQ - by default it's zero points
                # it can be overwritten later by the admin
                entry["points"] = 0
                driver.set_points(self, 0, entry["status"])

            else:
                # unknown driver status
                raise LookupError("Unknown driver status while assigning points: " + str(entry["status"]))

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

    def is_approved(self):
        session_data_table = self.config.get_db_connection().table('session_data')
        results = session_data_table.search(
            (where('season') == self.get_round().year) &
            (where('round') == self.get_round().num) &
            (where('session_name') == self.get_name())
        )
        if not results:
            return None
        return results[0]['approved']

    def store_approved_status(self, approved_status):
        session_data_table = self.config.get_db_connection().table('session_data')
        session_data_table.remove(
            (where('season') == self.get_round().year) &
            (where('round') == self.get_round().num) &
            (where('session_name') == self.get_name())
        )
        if approved_status:
            session_data_table.insert(
                {
                    'season': self.get_round().year,
                    'round': self.get_round().num,
                    'session_name': self.get_name(),
                    'approved': approved_status
                }
            )

    def load_point_adjustments(self):
        session_adjustments = self.config.get_db_connection().table('session_adjustments')
        list_of_adjustments = session_adjustments.search(
            (where('season') == self.get_round().year) &
            (where('round') == self.get_round().num) &
            (where('session_name') == self.get_name())
        )
        result = {}
        for item in list_of_adjustments:
            if not item['driver_name'] in result:
                result[item['driver_name']] = []
            result[item['driver_name']].append(item)

        return result

    def store_adjustment_of_driver_position(self, driver, positions):
        driver_name, driver_classes = self.get_driver_name_and_classes(driver)

        session_adjustments = self.config.get_db_connection().table('session_adjustments')
        session_adjustments.remove(
            (where('season') == self.get_round().year) &
            (where('round') == self.get_round().num) &
            (where('session_name') == self.get_name()) &
            (where('driver_name') == driver_name) &
            (where('type') == 'adjust_position')
        )
        session_adjustments.insert(
            {
                'season': self.get_round().year,
                'round': self.get_round().num,
                'session_name': self.get_name(),
                'driver_name': driver_name,
                'type': 'adjust_position',
                'positions': positions
            }
        )

    def store_adjustment_of_driver_points(self, driver, points):
        driver_name, driver_classes = self.get_driver_name_and_classes(driver)

        session_adjustments = self.config.get_db_connection().table('session_adjustments')
        session_adjustments.remove(
            (where('season') == self.get_round().year) &
            (where('round') == self.get_round().num) &
            (where('session_name') == self.get_name()) &
            (where('driver_name') == driver_name) &
            (where('type') == 'adjust_points')
        )
        session_adjustments.insert(
            {
                'season': self.get_round().year,
                'round': self.get_round().num,
                'session_name': self.get_name(),
                'driver_name': driver_name,
                'type': 'adjust_points',
                'points': points
            }
        )

    def clear_adjustments_for_driver(self, driver):
        driver_name, driver_classes = self.get_driver_name_and_classes(driver)

        session_adjustments = self.config.get_db_connection().table('session_adjustments')
        session_adjustments.remove(
            (where('season') == self.get_round().year) &
            (where('round') == self.get_round().num) &
            (where('session_name') == self.get_name()) &
            (where('driver_name') == driver_name)
        )
