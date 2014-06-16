class Driver():
    def __init__(self, name):
        self.name = name
        self.classes = set()
        self.points = {}

        # always add an empty class, which represents the overall championship
        self.classes.add("")

    def __eq__(self, another):
        return hasattr(another, 'name') and self.name == another.name

    def __hash__(self):
        return hash(self.name)

    def get_name(self):
        return self.name

    def add_classes(self, classes):
        self.classes |= classes

    def get_classes(self):
        return self.classes

    def get_points(self):
        return self.points

    def set_points(self, session, points, status, non_droppable):
        round_num = session.get_round()
        if not round_num in self.points:
            self.points[round_num] = {}

        data = {
            "points": points,
            "status": status
        }
        if non_droppable:
            data["non_droppable"] = True

        self.points[round_num][session] = data
