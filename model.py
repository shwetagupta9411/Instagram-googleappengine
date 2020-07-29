from google.appengine.ext import ndb

class User(ndb.Model):
    email = ndb.StringProperty()
    userName = ndb.StringProperty()
    following = ndb.JsonProperty()
    followers = ndb.JsonProperty()
    userImg = ndb.BlobKeyProperty()

class Comment(ndb.Model):
    commenter = ndb.StructuredProperty(User)
    commentDescription = ndb.StringProperty()
    createdAt = ndb.DateTimeProperty()

class Post(ndb.Model):
    image = ndb.BlobKeyProperty()
    content = ndb.StringProperty()
    owner = ndb.StructuredProperty(User)
    createdAt = ndb.DateTimeProperty()
    comments = ndb.StructuredProperty(Comment, repeated=True)
