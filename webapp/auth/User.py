import bcrypt
from tinydb import where


# noinspection PyMethodMayBeStatic
class User():
    def __init__(self, username):
        self.username = username

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


def password_hash(password):
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())


def matches_hash(password, password_hashed):
    return bcrypt.hashpw(password.encode('utf-8'), password_hashed.encode('utf-8')) == password_hashed.encode('utf-8')


def store_username_password(username, password, config):
    remove_by_username(username, config)
    users = config.get_db_connection().table('users')
    users.insert(
        {
            'username': username,
            'password': password_hash(password)
        }
    )


def load_all(config):
    users = config.get_db_connection().table('users')
    return users.all()


def load_by_username_password(username, password, config):
    users = config.get_db_connection().table('users')
    row = users.get(
        (where('username') == username)
    )
    if row and matches_hash(password, row['password']):
        return User(username)
    return None


def remove_by_username(username, config):
    users = config.get_db_connection().table('users')
    users.remove(
        (where('username') == username)
    )


def load_by_id(username, config):
    users = config.get_db_connection().table('users')
    results = users.search(
        (where('username') == username)
    )
    if results:
        return User(username)
    return None
