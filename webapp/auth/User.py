# noinspection PyMethodMayBeStatic
class User():
    def __init__(self, username, password):
        self.username = username
        self.password = password

    def is_authenticated(self):
        return True

    def is_active(self):
        return True

    def is_anonymous(self):
        return False

    def get_id(self):
        return unicode(self.username)

    def __repr__(self):
        return '<User %r>' % self.username


def load_by_username_password(username, password):
    return User(username, password)


def load_by_id(user_id):
    return User("a", "b")
