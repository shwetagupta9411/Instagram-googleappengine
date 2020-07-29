from operator import itemgetter
import webapp2
import jinja2
from google.appengine.api import users
import os
from google.appengine.ext import ndb
import logging
from model import User
from model import Post
from model import Comment
from webapp2_extras import sessions
from webapp2_extras import sessions_memcache
from datetime import datetime
from google.appengine.ext import blobstore
from google.appengine.ext.webapp import blobstore_handlers
from google.appengine.api import search
import time

JINJA_ENVIRONMENT = jinja2.Environment(loader=jinja2.FileSystemLoader(
    os.path.dirname(__file__)),extensions=["jinja2.ext.autoescape"], autoescape=True)
SPECIAL_CHAR = '''!    "       %       (       )
*   ,       -       |       /
[   ]       ]       ^       `
:   =       >       ?
{   }       ~       $'''

# To display messages
class BasicReqHandler(webapp2.RequestHandler):
    @webapp2.cached_property
    def session(self):
        """Returns a session using the default cookie key"""
        # return self.session_store.get_session()
        return self.session_store.get_session(
            name='mc_session',
            factory=sessions_memcache.MemcacheSessionFactory)

    def dispatch(self):
        # Get a session store for this request.
        self.session_store = sessions.get_store(request=self.request)
        try:
            # Dispatch the request.
            webapp2.RequestHandler.dispatch(self)
        finally:
            # Save all sessions.
            self.session_store.save_sessions(self.response)

    def add_message(self, message, level=None):
        self.session.add_flash(message, level, key='_messages')

    @webapp2.cached_property
    def messages(self):
        return self.session.get_flashes(key='_messages')

#This class is for comments on the post
class PostComment(BasicReqHandler):
    def post(self, id=None):
        comment = Comment()
        user = users.get_current_user()
        key_user = ndb.Key(User, user.email())
        user_details = key_user.get()
        if self.request.get("comment").strip() != "":
            comment.commenter = user_details
            comment.commentDescription = self.request.get("comment").strip()
            comment.createdAt = datetime.now()
            comment = comment.put()
            commentedPost = Post.get_by_id(int(id))
            commentedPost.comments.append(comment.get())
            commentedPost.put()
            time.sleep(0.1)
        else:
            self.add_message("Please don't enter empty string", "danger")

        if self.request.get("ad").strip() == "postDetail":
            self.redirect('/post/'+id, abort=False)
        else:
            self.redirect('/', abort=False)


# To upload preofile picture
class UploadDP(blobstore_handlers.BlobstoreUploadHandler):
    def post(self):
        upload = self.get_uploads()[0]
        user = users.get_current_user()
        if user:
            key_user = ndb.Key(User, user.email())
            user_details = key_user.get()
            user_details.userImg = upload.key()
            user_details.put()
            urlRed = "/userProfile?user=%s" % (user_details.email)
            self.redirect(urlRed, abort=False)

# This class is to create a post
class CreatePost(blobstore_handlers.BlobstoreUploadHandler):
    def post(self):
        upload = self.get_uploads()[0]
        user = users.get_current_user()
        if user:
            key_user = ndb.Key(User, user.email())
            user_details = key_user.get()
            post = Post()
            post.owner = user_details
            post.image = upload.key()
            post.content = self.request.get("content")
            post.createdAt = datetime.now()
            post.put()
            time.sleep(0.1)
        self.redirect('/', abort=False)

# This is the class to view the photo
class ViewPhotoHandler(blobstore_handlers.BlobstoreDownloadHandler):
    def get(self, photo_key):
        if not blobstore.get(photo_key):
            self.error(404)
        else:
            self.send_blob(photo_key)

# This class is for adding the user name
class UpdateUserName(BasicReqHandler):
    def tokenize_autocomplete(self, phrase):
        a = []
        for word in phrase.split():
            j = 1
            while True:
                for i in range(len(word) - j + 1):
                    a.append(word[i:i + j])
                if j == len(word):
                    break
                j += 1
        return a

    def post(self):
        user = users.get_current_user()
        is_special_char_present = False
        for char in SPECIAL_CHAR.split():
             if char in self.request.get("userName").strip():
                 is_special_char_present = True
                 break

        if user:
            if is_special_char_present:
                self.add_message('Only . and _ are allowed in user name', 'danger')
                self.redirect('/', abort=False)
                return

            rec = User.query(User.userName == self.request.get("userName").strip()).fetch(1)
            if len(rec):
                self.add_message('User name already exists.', 'danger')
            else:
                key_user = ndb.Key(User, user.email())
                key_user = key_user.get()
                key_user.userName = self.request.get("userName").strip()
                u_key = key_user.put()
                index = search.Index(name='search_user')
                doc_id = u_key.urlsafe()
                emaildoc = user.email().split("@")[0]
                emaildoc = ','.join(self.tokenize_autocomplete(emaildoc))
                uNameDoc = ','.join(self.tokenize_autocomplete(self.request.get("userName").strip()))
                document = search.Document(
                    doc_id=doc_id,
                    fields=[search.TextField(name='name', value=uNameDoc), search.TextField(name='email', value=emaildoc)])
                index.put(document)

        self.redirect('/', abort=False)

# This class is for follow and unfollow feature
class FollowUnfollow(BasicReqHandler):
    def get(self):
        userCurrent = users.get_current_user()
        userProf = self.request.get("user").strip()
        key_userProf = ndb.Key(User, userProf)
        key_userProf = key_userProf.get()
        key_userCurrent = ndb.Key(User, userCurrent.email())
        key_userCurrent = key_userCurrent.get()

        if self.request.get("btn").strip() == "Follow":
            if key_userCurrent.following:
                if userProf not in key_userCurrent.following:
                    key_userCurrent.following.append(userProf)
                else:
                    self.add_message('Already following this user.', 'danger')
            else:
                key_userCurrent.following = [userProf]
            key_userCurrent.put()

            if key_userProf.followers:
                if userCurrent.email() not in key_userProf.followers:
                    key_userProf.followers.append(userCurrent.email())
            else:
                key_userProf.followers = [userCurrent.email()]
            key_userProf.put()

        elif self.request.get("btn").strip() == "Unfollow":
            if key_userCurrent.following:
                if userProf in key_userCurrent.following:
                    key_userCurrent.following.remove(userProf)
                else:
                    self.add_message('You are not following this user.', 'danger')
                key_userCurrent.put()

            if key_userProf.followers:
                if userCurrent.email() in key_userProf.followers:
                    key_userProf.followers.remove(userCurrent.email())
            key_userProf.put()


        urlRed = "/userProfile?user=%s" % (userProf)
        self.redirect(urlRed, abort=False)

# This class is used to display the user profile.
class UserProfile(BasicReqHandler):
    def get(self):
        user = users.get_current_user()
        followBtn = "Follow"
        btnIcon = "plus"
        btn = "success"
        followingUsers = []
        followerUsers = []
        if user:
            url = users.create_logout_url(self.request.uri)
            url_string = "Logout"
            upload_url = blobstore.create_upload_url("/upload_DP")
            usekey = self.request.get("user").strip()
            key_user = ndb.Key(User, usekey)
            userProfile = key_user.get()
            userPosts = Post.query(Post.owner.email == userProfile.email).order(-Post.createdAt).fetch()
            key_userCurrent = ndb.Key(User, user.email())
            key_userCurrent = key_userCurrent.get()
            if userProfile.following:
                for uFlng in userProfile.following:
                    ukeyFollow = ndb.Key(User, uFlng)
                    followingUsers.append(ukeyFollow.get())

            if userProfile.followers:
                for uFlwer in userProfile.followers:
                    ukeyFollower = ndb.Key(User, uFlwer)
                    followerUsers.append(ukeyFollower.get())

            if key_userCurrent.following:
                if usekey in key_userCurrent.following:
                    followBtn = "Unfollow"
                    btnIcon = "minus"
                    btn = "danger"

        else:
            url = users.create_login_url(self.request.uri)
            url_string = "Login"
            self.redirect("/", abort=False)
            return

        template_values = {
        "url": url,
        "url_string": url_string,
        "user": user,
        "userPosts" : userPosts,
        "userProfile" : userProfile,
        "currentUserProf": key_userCurrent,
        "followBtn" : followBtn,
        "btnIcon" : btnIcon,
        "btn" : btn,
        "followingUsers": followingUsers,
        "followerUsers": followerUsers,
        "upload_url": upload_url,
        "messages": self.messages,
        }
        template = JINJA_ENVIRONMENT.get_template("/Instagram/userProfile.html")
        self.response.write(template.render(template_values))

# This class is used for user search
class UserSearch(BasicReqHandler):
    def get(self):
        user = users.get_current_user()
        searchRes = []
        userDetails = []
        currentUserProf = None
        searchedString = self.request.get("username").strip()
        searchedStringOrig = self.request.get("username").strip()
        if '@' in searchedString:
            searchedString = searchedString.split("@")[0]
        is_special_char_present = False
        for char in SPECIAL_CHAR.split():
             if char in searchedString:
                 is_special_char_present = True
                 break

        if user:
            currentUserProf = ndb.Key(User, user.email())
            currentUserProf = currentUserProf.get()
            url = users.create_logout_url(self.request.uri)
            url_string = "Logout"

            if is_special_char_present:
                self.add_message('Invalid user name passed in search string', 'danger')
            else:
                if searchedString != "":
                    results_name = search.Index(name="search_user").search("name:%s" % (searchedString))
                    results_email = search.Index(name="search_user").search("email:%s" % (searchedString))

                    for res in results_name.results:
                        if res.doc_id not in searchRes:
                            searchRes.append(res.doc_id)

                    for resemail in results_email.results:
                        if resemail.doc_id not in searchRes:
                            searchRes.append(resemail.doc_id)

                    for urlkey in searchRes:
                        user_detail = ndb.Key(urlsafe=urlkey)
                        if user_detail.get():
                            userDetails.append(user_detail.get())
                else:
                    self.add_message('Please enter a valid user name', 'danger')

        else:
            url = users.create_login_url(self.request.uri)
            url_string = "Login"
            self.redirect("/", abort=False)
            return


        template_values = {
        "url": url,
        "url_string": url_string,
        "user": user,
        "userDetails" : userDetails,
        "currentUserProf": currentUserProf,
        "searchedString" : searchedStringOrig,
        "messages": self.messages,
        }
        template = JINJA_ENVIRONMENT.get_template("/Instagram/userSearch.html")
        self.response.write(template.render(template_values))

# To show the posts on new page
class ShowPost(BasicReqHandler):
    def get(self, id=None):
        post = Post.get_by_id(int(id))
        user = users.get_current_user()
        get_user = None
        if user:
            key_user = ndb.Key(User, user.email())
            get_user = key_user.get()
            url = users.create_logout_url(self.request.uri)
            url_string = "Logout"
        else:
            url = users.create_login_url(self.request.uri)
            url_string = "Login"
            self.redirect("/", abort=False)

        template_values = {
        "url": url,
        "url_string": url_string,
        "user": user,
        "post": post,
        "currentUserProf": get_user,
        "messages": self.messages,
        }
        template = JINJA_ENVIRONMENT.get_template("/Instagram/post.html")
        self.response.write(template.render(template_values))

# welcome to application class
class MainPage(BasicReqHandler):
    def get(self):
        self.response.headers["Content-Type"] = "text/html"
        url = ""
        url_string = ""
        user = users.get_current_user()
        userName = None
        allpost = None
        get_user = None
        upload_url = blobstore.create_upload_url("/upload_photo")
        if user:
            url = users.create_logout_url(self.request.uri)
            url_string = "Logout"
            allUser = [user.email()]
            key_user = ndb.Key(User, user.email())
            if not key_user.get():
                userModel = User(key=key_user, email=user.email())
                userModel.put()

            else:
                get_user = key_user.get()
                userName = get_user.userName
                userFollowers = get_user.following
                if userFollowers:
                    for el in userFollowers:
                        allUser.append(el)
                allpost = Post.query(Post.owner.email.IN(allUser)).order(-Post.createdAt).fetch(50)

        else:
            url = users.create_login_url(self.request.uri)
            url_string = "Login"

        template_values = {
        "url": url,
        "url_string": url_string,
        "user": user,
        "userName": userName,
        "messages": self.messages,
        "upload_url": upload_url,
        "allpost": allpost,
        "currentUserProf": get_user
        }
        template = JINJA_ENVIRONMENT.get_template("/Instagram/welcome.html")
        self.response.write(template.render(template_values))


config = {}
config["webapp2_extras.sessions"] = {
    "secret_key": "_session_key",
}

app = webapp2.WSGIApplication(
    [
        ("/", MainPage),
        ("/update_user_name", UpdateUserName),
        ('/upload_photo', CreatePost),
        ('/userProfile', UserProfile),
        ('/view_photo/([^/]+)?', ViewPhotoHandler),
        ('/search_user', UserSearch),
        ('/follow_unfollow', FollowUnfollow),
        ('/add_comment/(\d+)', PostComment),
        ('/post/(\d+)', ShowPost),
        ('/upload_DP', UploadDP),

    ],
    debug=True,
    config=config)
