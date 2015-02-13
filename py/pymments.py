from datetime import datetime
import json
import logging
import os
import sqlite3
import urllib.parse
import uuid

logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger(__name__)

file = os.path.join(os.path.dirname(__file__), 'comments.sqlite3')
log.info(file)
connection = sqlite3.connect(file)

found_comments = False
found_users = False
cursor = connection.cursor()
cursor.execute('SELECT name FROM sqlite_master')
for row in cursor:
    if row[0] == 'users':
        found_users = True
    elif row[0] == 'comments':
        found_comments = True

if not found_users:
    cursor.execute('''
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            password TEXT,
            name TEXT UNIQUE
        )
    ''')

if not found_comments:
    cursor.execute('''
        CREATE TABLE comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            itemId INTEGER,
            parentId INTEGER,
            userId INTEGER,
            message TEXT,
            time INTEGER
        )
    ''')

class User:

    def __init__(self, id, name, password):
        self.id = id
        self.name = name
        self.password = password

    @property
    def json(self):
        return {
            'id': self.id,
            'name': self.name,
        }

class Comment:

    def __init__(self, id, itemId, parent, user, message, time):
        self.id = id
        self.itemId = itemId
        self.parent = parent
        self.user = user
        self.message = message
        self.time = time

    @property
    def json(self):
        return {
            'id': self.id,
            'itemId': self.itemId,
            'parentId': self.parent.id if self.parent else None,
            'user': self.user.json,
            'message': self.message,
            'time': self.time.timestamp(),
        }

def create_user(name):
    password = uuid.uuid4().hex
    cursor.execute('INSERT INTO users (name, password) VALUES (?, ?)', (name, password))
    connection.commit()
    id = cursor.lastrowid
    return User(id, name, password)

def get_user(id, password):
    cursor.execute('SELECT name FROM users WHERE id = ? AND password = ?', (id, password))
    row = cursor.fetchone()
    if row is None:
        return None
    return User(id, row[0], password)

def change_username(id, password, name):
    user = get_user(id, password)
    assert user is not None
    cursor.execute('UPDATE users SET name = ? WHERE id = ?', (name, id))
    connection.commit()
    user.name = name
    return user

def create_comment(itemId, parentId, userId, userPassword, message):
    user = get_user(userId, userPassword)
    assert user is not None
    time = datetime.now()
    cursor.execute('INSERT INTO comments (itemId, parentId, userId, message, time) VALUES (?, ?, ?, ?, ?)', (itemId, parentId, user.id, message, time.timestamp()))
    id = cursor.lastrowid
    connection.commit()
    return Comment(id, itemId, None, user, message, time)

def comments(itemId, lastId):
    time_threshold = 0
    if int(lastId):
        cursor.execute('SELECT time FROM comments WHERE id = ?', (lastId,))
        time_threshold = cursor.fetchone()[0]
    cursor.execute('''
        SELECT
            u.id, u.name, c.id, c.message, c.time
        FROM
            users u
            INNER JOIN comments c on c.userId = u.id
        WHERE
            c.itemId = ?
            AND c.time > ?
        ORDER BY c.time ASC
        LIMIT 10
    ''', (itemId, time_threshold))
    return map(lambda row: Comment(
        row[2],
        itemId,
        None,
        User(
            row[0],
            row[1],
            None
        ),
        row[3],
        datetime.fromtimestamp(int(row[4])),
    ), cursor)


def application(env, start_response):
    try:
        if env['REQUEST_METHOD'] == 'POST':
            args = urllib.parse.parse_qs(str(env['wsgi.input'].readline(), 'UTF-8'))
            if args['op'][0] == 'user':
                user = create_user(args['name'][0])
                body = {
                    'id': user.id,
                    'name': user.name,
                    'password': user.password,
                }
            elif args['op'][0] == 'username':
                user = change_username(args['id'][0], args['password'][0], args['name'][0])
                body = user.json
            elif args['op'][0] == 'comment':
                body = create_comment(
                    args['itemId'][0],
                    args['parentId'][0],
                    args['userId'][0],
                    args['userPassword'][0],
                    args['message'][0]
                ).json
        else:
            args = urllib.parse.parse_qs(env['QUERY_STRING'], encoding='UTF-8')
            log.debug(args)
            if args['op'][0] == 'comments':
                body = []
                for comment in comments(args['itemId'][0], args['lastId'][0]):
                    body.append(comment.json)
        log.debug(args)
        start_response('200 OK', [('Content-Type','application/json')])
        return [json.dumps(body).encode('UTF-8')]
    except Exception as e:
        start_response('500 Internal Server Error', [('Content-Type','text/html')])
        log.exception(e)


## from abc import abstractmethod, ABCMeta
## 
## 
## class User:
## 
##     def __init__(self, name):
##         self.name = name
## 
## 
## class Comment:
## 
##     def __init__(self, parent, user, text, time):
##         self.parent = parent
##         self.user = user
##         self.item = item
##         self.text = text
##         self.time = time
## 
## 
## class Item:
## 
##     def __init__(self, storage, id):
##         self.storage = storage
##         self.id = id
## 
##     @property
##     def comments(self):
##         pass
## 
## 
## class Storage(metaclass=ABCMeta):
##     
##     def item(self, id):
##         return Item(self, id)
## 
##     @abstractmethod
##     def comment(self, item_id, comment_id):
##         pass
## 
##     @abstractmethod
##     def comments(self, item_id):
##         pass
## 
##     @abstractmethod
##     def comment_count(self, item_id):
##         pass
## 
## 
## class SqliteCommentsIterator:
## 
##     def __init__(self, cursor):
##         self.cursor = cursor
##         self.remaining_rows = None
##         self.return_count = 0
## 
##     def __iter__(self):
##         return self
## 
##     def __next__(self):
##         if self.remaining_rows is not None:
##             try:
##                 row = self.remaining_rows.pop(0)
##             except IndexError:
##                 raise StopIteration()
##         else:
##             row = next(self.cursor)
##         self.return_count += 1
##         return Comment(*row)
## 
##     def __len__(self):
##         if self.remaining_rows is None:
##             self.remaining_rows = self.cursor.fetchall()
##         return self.return_count + len(self.remaining_rows)
## 
## 
## class SqliteStorage(Storage):
## 
##     def __init__(self, file):
##         self.file = file
##         self._cursor = None
## 
##     def comments(self, item_id):
##         cursor = self.connection.cursor()
##         cursor.execute("""
##             SELECT parent, user, item, text, time FROM comment WHERE item = ?
##         """, item_id)
##         return SqliteCommentsIterator(cursor)
## 
##     def comment_count(self, item_id):
##         cursor = self.connection.cursor()
##         cursor.execute("SELECT COUNT(*) FROM comment WHERE item = ?", item_id)
##         return cursor.fetchone()[0]
## 
##     @property
##     def connection(self):
##         if not self._connection:
##             self._connection = sqlite3.connect(self.file)
##         return self._connection


