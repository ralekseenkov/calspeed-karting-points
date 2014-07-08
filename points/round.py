import requests
import json
import os
import re
from operator import methodcaller
from os import listdir
from os.path import isfile, isdir, join
from session import Session
from tinydb import where


class Round():
    def __init__(self, config, year, num):
        self.config = config
        self.year = year
        self.num = num
        self.sessions_by_type = {}
        self.qualifier = None
        self.main_merged = None

    def get_num(self):
        return self.num

    @staticmethod
    def get_num_letter(s):
        if re.match("^[0-9]?[A-Z]?$", s):
            return s
        return ""

    @staticmethod
    def get_identifier(name):
        # remove the first word from the event name (e.g. "Heat 1 - D")
        result = name.split(' ', 1)[1]

        # remove all spaces and dashes
        result = result.replace(" ", "")
        result = result.replace("-", "")

        # return uppercase
        return result.upper()

    def parse_session_data_from_filename(self, name_orig, file_extension):
        # uppercase file name
        name = name_orig.upper()

        # skip files with incorrect extension
        if not name.endswith(file_extension.upper()):
            return None

        # ignore file which contains metadata for the round
        if name == 'ROUND.JSON':
            return None

        # remove file extension and all spaces
        name = name.replace(" ", "")
        name = name.replace(file_extension.upper(), "")

        # split by "-"
        tokens = name.split("-")

        # keywords to look for
        keywords = [
            "QUALIFY",  # qualifying is given as multiple sessions, needs to be merged into one
            "MAIN",  # individual main races
            "HEAT"  # individual heat races
        ]

        # read session
        stype = ""
        sid = ""
        for token in tokens:
            # collect ids
            sid += self.get_num_letter(token)

            # check for session type
            for k in keywords:
                if k in token:
                    stype = k
                    sid += self.get_num_letter(token.replace(k, ""))
                    break

        skey = stype
        if len(sid) > 0:
            skey += "-" + sid

        return {"type": stype, "id": sid, "key": skey, "filename": name_orig}

    def get_directory(self):
        return self.config.get_db_directory() + "/races/" + str(self.year) + "-round-" + str(self.num)

    def read_session(self, sessions, stype, sid=""):
        # compose key
        key = stype
        if len(sid) > 0:
            key += "-" + sid

        if not key in sessions:
            raise LookupError("Session data not found: " + key)

        # look up session data
        session_data = sessions[key]

        # read this session from a file
        session_obj = Session(self.config, self, session_data["type"], session_data["id"], session_data["filename"])
        session_obj.read()

        # create list of sessions for each type
        stype = session_data["type"]
        if not stype in self.sessions_by_type:
            self.sessions_by_type[stype] = []
        self.sessions_by_type[stype].append(session_obj)

    def exists(self):
        dirname = self.get_directory()
        if not isdir(dirname):
            return False
        if self.get_mylaps_id() is None:
            return False
        jsonfiles = [f for f in listdir(dirname) if isfile(join(dirname, f)) and f.upper().endswith('.JSON')]
        return len(jsonfiles) > 0

    def read(self):

        # determine the directory
        dirname = self.get_directory()

        # read all sessions
        onlyfiles = [f for f in listdir(dirname) if isfile(join(dirname, f))]

        # put session data into map
        sessions = {}
        for f in onlyfiles:
            session_data = self.parse_session_data_from_filename(f, ".JSON")
            if session_data:
                key = session_data["key"]
                if key in sessions:
                    raise NameError("Found duplicate data: " + key)
                sessions[key] = session_data

        # qualifying sessions (read and merge into one)
        for qualifyNum in xrange(6):
            self.read_session(sessions, "QUALIFY", str(qualifyNum + 1))

        qualifying_merged = Session(self.config, self, "QUALIFYING")
        for qualify_session in self.sessions_by_type["QUALIFY"]:
            qualifying_merged.merge_with(qualify_session)
        qualifying_merged.remove_not_finished()
        qualifying_merged.remove_na_best_time()
        qualifying_merged.sort_by_best_time()
        qualifying_merged.reassign_positions()
        qualifying_merged.recalculate_best_lap_gaps()
        self.sessions_by_type["QUALIFYING"] = [qualifying_merged]

        # heats
        for heatNum in ['1', '2']:
            for heatLetter in ['A', 'B', 'C', 'D']:
                self.read_session(sessions, "HEAT", heatNum + heatLetter)

        # mains
        for mainLetter in ['A', 'B', 'C', 'D']:
            self.read_session(sessions, "MAIN", mainLetter)

    def get_url(self, mylaps_id):
        return self.config.get_mylaps_event_page_url() + str(mylaps_id)

    def download(self, mylaps_id):
        response = requests.get(self.get_url(mylaps_id))
        data = json.loads(response.content)

        # if there is no event, just exit
        if "event" not in data:
            return False

        # retrieve name of the event
        print "  [x] Found '%s'" % data["event"]["name"]

        # determine the directory
        dirname = self.get_directory()
        if not os.path.exists(dirname):
            os.makedirs(dirname)

        # store the json
        with open(dirname + "/round.json", "w") as outfile:
            json.dump(data, outfile, indent=4)

        # iterate over available sessions
        for group in data["groups"]:
            for session in group["sessions"]:
                # Determine name
                stype_orig = session["type"]

                if stype_orig == "practice":
                    stype = "practice"
                elif stype_orig == "qualify":
                    stype = "qualify"
                elif stype_orig == "race":
                    if "Heat" in session["name"]:
                        stype = "heat"
                    elif "Main" in session["name"]:
                        stype = "main"
                    else:
                        raise NameError("Unrecognized race name: " + session["name"])
                elif stype_orig == "points":
                    # Skip sessions which represent aggregation of other sessions
                    # E.g. http://www.mylaps.com/en/events/951921
                    continue
                else:
                    raise NameError("Unrecognized session type: " + stype_orig)

                sid = self.get_identifier(session["name"])
                if not sid:
                    raise NameError("Can't parse out session identifier: " + session["name"])
                if sid == "MERGE":
                    # Skip sessions which represent aggregation of other sessions.
                    # E.g. http://www.mylaps.com/en/events/951921
                    continue

                # Download session
                session_obj = Session(self.config, self, stype, sid)
                session_obj.download(session["id"])

        return True

    @staticmethod
    def get_single_session(sessions):
        if len(sessions) == 1:
            return sessions[0]
        raise LookupError("Expected only one qualifier, but found many: " + str(sessions))

    def get_sessions_by_type(self):
        return self.sessions_by_type

    def calc_points(self, drivers, season_data):

        # calculate points for the qualifier
        self.qualifier = self.get_single_session(self.sessions_by_type["QUALIFYING"])
        self.qualifier.calc_points(drivers, season_data)

        # calculate points for each heat separately
        for heat in self.sessions_by_type["HEAT"]:
            heat.calc_points(drivers, season_data)

        # mains - should be merged into one session and then awarded points
        self.main_merged = Session(self.config, self, "MAIN")
        for main in sorted(self.sessions_by_type["MAIN"], key=methodcaller('get_id')):
            self.main_merged.merge_with(main)

        self.main_merged.remove_duplicate_drivers_advanced_to_mains(season_data)
        self.main_merged.reassign_positions()
        self.main_merged.calc_points(drivers, season_data)

    def store_points(self, suffix=""):
        # store points for the qualifier
        self.qualifier.store_points(suffix)

        # store points for the heats
        for heat in self.sessions_by_type["HEAT"]:
            heat.store_points(suffix)

        # store points for the merged main
        self.main_merged.store_points(suffix)

    def load_points_session(self, stype, sid=""):
        session_obj = Session(self.config, self, stype, sid)
        session_obj.load_points()

        # create list of sessions for each type
        if not stype in self.sessions_by_type:
            self.sessions_by_type[stype] = []
        self.sessions_by_type[stype].append(session_obj)

    def load_points(self):

        # load all sessions
        self.load_points_session("QUALIFYING")

        for heatNum in ['1', '2']:
            for heatLetter in ['A', 'B', 'C', 'D']:
                self.load_points_session("HEAT", heatNum + heatLetter)

        self.load_points_session("MAIN")


    @staticmethod
    def generate_session_keys():

        # noinspection PyListCreation
        keys = []
        keys.append(("QUALIFYING", ""))

        for heatNum in ['1', '2']:
            for heatLetter in ['A', 'B', 'C', 'D']:
                keys.append(("HEAT", heatNum + heatLetter))

        keys.append(("MAIN", ""))
        return keys

    def get_mylaps_id(self):
        round_urls = self.config.get_db_connection().table('round_mylap_ids')
        results = round_urls.search(
            (where('season') == self.year) &
            (where('round') == self.num)
        )
        if not results:
            return None
        return results[0]['id']

    def get_mylaps_url_web(self):
        return self.config.get_mylaps_event_page_url_web() + self.get_mylaps_id()

    def store_mylaps_id(self, mylaps_id):
        round_urls = self.config.get_db_connection().table('round_mylap_ids')
        round_urls.remove(
            (where('season') == self.year) &
            (where('round') == self.num)
        )
        round_urls.insert(
            {
                'season': self.year,
                'round': self.num,
                'id': mylaps_id
            }
        )

    def delete_stored_data(self):
        # drop data from tinydb
        round_urls = self.config.get_db_connection().table('round_mylap_ids')
        round_urls.remove(
            (where('season') == self.year) &
            (where('round') == self.num)
        )

        # delete all jsons
        dirname = self.get_directory()
        jsonfiles = [f for f in listdir(dirname) if isfile(join(dirname, f)) and f.upper().endswith('.JSON')]
        for f in jsonfiles:
            os.remove(dirname + '/' + f)

    def count_approved_sessions(self):
        session_data_table = self.config.get_db_connection().table('session_data')
        results = session_data_table.search(
            (where('season') == self.year) &
            (where('round') == self.num)
        )
        if not results:
            return 0
        return len(results)

    def count_total_sessions(self):
        return len(self.generate_session_keys())

    def is_approved(self):
        return self.count_approved_sessions() >= self.count_total_sessions()

    def load_point_adjustments(self):
        session_adjustments = self.config.get_db_connection().table('session_adjustments')
        list_of_adjustments = session_adjustments.search(
            (where('season') == self.year) &
            (where('round') == self.num)
        )
        result = {}
        for item in list_of_adjustments:
            if not item['driver_name'] in result:
                result[item['driver_name']] = []
            result[item['driver_name']].append(item)

        return result
