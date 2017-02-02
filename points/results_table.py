from operator import itemgetter
import copy


class ResultsTable():
    def __init__(self, total_rounds, drop_rounds, rounds_list):
        self.total_rounds = total_rounds
        self.drop_rounds = drop_rounds
        self.rounds_list = rounds_list
        self.drivers = []
        self.table = []
        self.ignore_last_round = False
        self.driver_prev_position_map = {}
        self.round_points_empty = []

    def use_drivers(self, drivers):
        self.drivers = drivers

    def get_table(self):
        return self.table

    def set_table(self, table):
        self.table = table

    def strip_to_round(self, round_num):
        # Keep only current round
        for row in self.table:
            row["current_round"] = [c for c in row["rounds"] if c["round"] == round_num][0]

        # Keep only drivers who participated in the current round
        self.table = [c for c in self.table if "detailed_points" in c["current_round"]]

        # Sort by points in the current round
        self.table = sorted(self.table, key=lambda x: (x["current_round"]["points"]), reverse=True)

        # assign positions
        position = 1
        line_prev = None
        for line in self.table:
            if line_prev is None or line["current_round"]["points"] != line_prev["current_round"]["points"]:
                line["position"] = position
            else:
                line["position"] = line_prev["position"]
            line_prev = line
            position += 1

    @staticmethod
    def find_detailed_points(line, stype, sid=""):
        for entry in line["current_round"]["detailed_points"]:
            if entry["stype"] == stype and sid in entry["sid"]:
                return entry["points"] if entry["points"] > 0 else ""
        return ""

    @staticmethod
    def is_line_non_droppable(line):
        for entry in line["current_round"]["detailed_points"]:
            if "non_droppable" in entry:
                return True
        return False

    def set_ignore_last_round(self):
        self.ignore_last_round = True

    def get_driver_position_map(self):
        result = {}
        for line in self.table:
            result[line["driver"]] = line["position"]
        return result

    def set_driver_prev_position_map(self, position_map):
        self.driver_prev_position_map = position_map

    def process(self):

        # figure out the number of active rounds
        active_rounds = set()
        for driver in self.drivers:
            for round_obj in driver.get_points():
                if round_obj.exists():
                    idx = int(round_obj.get_num()) - 1
                    if idx < 0 or idx >= self.total_rounds:
                        raise IndexError("Invalid round: " + round_obj.get_num())
                    active_rounds.add(idx)

        # if we need to ignore last round, figure out which round is the last and drop it
        if self.ignore_last_round:
            last_round = None
            for r in self.rounds_list:
                idx = int(r.get_num()) - 1
                if idx in active_rounds:
                    if last_round is None or r.get_date() > last_round.get_date():
                        last_round = r
            if last_round is not None:
                active_rounds.remove(int(last_round.get_num()) - 1)

        # process points
        for driver in self.drivers:
            # init driver points for each round
            round_points = []
            for round_num in xrange(self.total_rounds):
                round_points.append(
                    {
                        "round": round_num + 1,
                        "points": 0,
                        "dropped": False,
                        "exists": round_num in active_rounds
                    }
                )

            self.round_points_empty = copy.deepcopy(round_points)

            # go through each round and update points
            for round_obj in driver.get_points():

                # get index of the round
                idx = int(round_obj.get_num()) - 1

                # skip, if it's not an active round
                if not idx in active_rounds:
                    continue

                # iterate over all sessions and accumulate data
                item = round_points[idx]

                item["detailed_points"] = []
                for session in driver.get_points()[round_obj]:
                    points = driver.get_points()[round_obj][session]["points"]
                    non_droppable = "non_droppable" in driver.get_points()[round_obj][session]

                    detailed_points = {
                        "stype": session.get_type(),
                        "sid": session.get_id(),
                        "points": points
                    }

                    if non_droppable:
                        item["non_droppable"] = True
                        detailed_points["non_droppable"] = True

                    item["points"] += points
                    item["detailed_points"].append(detailed_points)

            # we don't want to drop full amount when the total number of rounds is very small
            drops = self.drop_rounds
            if len(active_rounds) <= 2:
                drops = 0
            elif len(active_rounds) == 3:
                drops = min(drops, 1)

            # drop some amount of worst rounds
            for drop_round in xrange(drops):
                worst_item = None
                for item in round_points:
                    # do not drop rounds which are marked as non-droppable
                    if "non_droppable" in item:
                        continue

                    # pick the worst round to be dropped
                    if not item["dropped"] and item["exists"] \
                            and (worst_item is None or item["points"] < worst_item["points"]):
                        worst_item = item
                if worst_item:
                    worst_item["dropped"] = True

            # calculate total points and dropped points
            total_points = sum(r["points"] for r in round_points if not r["dropped"])
            dropped_points = sum(r["points"] for r in round_points if r["dropped"])

            # add line into the table
            table_line = {
                "driver": driver.get_name(),
                "rounds": round_points,
                "dropped_points": dropped_points,
                "total_points": total_points
            }

            self.table.append(table_line)

        # sort the table
        self.table = sorted(self.table, key=itemgetter("total_points"), reverse=True)

        # assign positions
        position = 1
        line_prev = None
        for line in self.table:
            if line_prev is None or line["total_points"] != line_prev["total_points"]:
                line["position"] = position
            else:
                line["position"] = line_prev["position"]
            line_prev = line
            position += 1

        # look up position of each driver before the round and see how it got changed
        for line in self.table:
            if line["driver"] in self.driver_prev_position_map:
                pos_prev = self.driver_prev_position_map[line["driver"]]
                line["position_change"] = line["position"] - pos_prev
            else:
                line["position_change"] = ""
