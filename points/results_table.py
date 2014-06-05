from operator import itemgetter


class ResultsTable():
    def __init__(self, total_rounds, drop_rounds):
        self.total_rounds = total_rounds
        self.drop_rounds = drop_rounds
        self.lines = []
        self.table = []

    def add_line(self, line):
        self.lines.append(line)

    def get_table(self):
        return self.table

    def set_table(self, table):
        self.table = table

    @staticmethod
    def is_integer(s):
        try:
            int(s)
            return True
        except ValueError:
            return False

    def strip_to_round(self, round_num):
        # Keep only current round
        for row in self.table:
            row["current_round"] = [c for c in row["rounds"] if c["round"] == round_num][0]

        # Keep only drivers who participated in the current round
        self.table = [c for c in self.table if "detailed_points" in c["current_round"]]

        # Sort by points in the current round
        self.table = sorted(self.table, key=lambda x: (x["current_round"]["points"]), reverse=True)

        # Assign positions
        position = 1
        for row in self.table:
            if self.is_integer(row["position"]):
                row["position"] = str(position)
            position += 1

    @staticmethod
    def find_detailed_points(line, stype, sid=""):
        for entry in line["current_round"]["detailed_points"]:
            if entry["stype"] == stype and sid in entry["sid"]:
                return entry["points"] if entry["points"] > 0 else ""
        return ""

    def process(self):

        for driver in self.lines:
            # init driver points for each round
            round_points = []
            for round_num in range(self.total_rounds):
                round_points.append({"round": round_num + 1, "points": 0, "dropped": False})

            # go through each round and update points
            for round_obj in driver.get_points():

                # get index of the round
                idx = int(round_obj.get_num()) - 1
                if idx < 0 or idx >= self.total_rounds:
                    raise IndexError("Invalid round: " + round_obj.get_num())

                # iterate over all sessions and accumulate data
                item = round_points[idx]

                item["detailed_points"] = []
                for session in driver.get_points()[round_obj]:
                    points = driver.get_points()[round_obj][session]["points"]
                    item["points"] += points
                    item["detailed_points"].append(
                        {"stype": session.get_type(), "sid": session.get_id(), "points": points})

            # drop some amount of worst rounds
            for drop_round in range(self.drop_rounds):
                worst_item = None
                for item in round_points:
                    if not item["dropped"] and (worst_item is None or item["points"] < worst_item["points"]):
                        worst_item = item
                worst_item["dropped"] = True

            # calculate total points and dropped points
            total_points = sum(r["points"] for r in round_points if not r["dropped"])
            dropped_points = sum(r["points"] for r in round_points if r["dropped"])

            # add line into the table
            table_line = {
                "driver": driver.get_name(),
                "rounds": round_points,
                "dropped_points": dropped_points,
                "total_points": total_points,
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
