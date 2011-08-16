#!/usr/bin/env python

import os
from random import choice
from datetime import datetime, timedelta

from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.ext.webapp import template
from google.appengine.ext import db

class Registration(db.Model):
    device_id = db.StringProperty(required=True)
    reg_code = db.StringProperty(required=True)
    service = db.StringProperty()
    oauth_token = db.StringProperty(required=True)
    oauth_verifier = db.StringProperty()
    create_time = db.DateTimeProperty(auto_now_add=True)
    reg_complete = db.BooleanProperty(default=False)
    
class RegistrationHist(db.Model):
    device_id = db.StringProperty(required=True)
    create_time = db.DateTimeProperty(auto_now_add=True)
    reg_complete = db.BooleanProperty(default=False)

class LinkHandler(webapp.RequestHandler):
    def get(self):
        self.redirect("https://secure.smugmug.com/signup.mg?Coupon=2TqKwSOXw5HeU")

class RegCodeHandler(webapp.RequestHandler):
    def get(self):
        device_id = self.request.get("deviceID")
        oauth_token = self.request.get("oauth_token")
        reg_code = self.gen_random_string()
        service = self.request.get("service",default_value="smugmug")
        
        reg = Registration(reg_code=reg_code,
                           device_id=device_id,
                           service=service,
                           oauth_token=oauth_token)
        reg.put()

        self.response.out.write("<result>")
        self.response.out.write("<status>success</status>")
        self.response.out.write("<regCode>"+reg_code+"</regCode>")
        self.response.out.write("<retryInterval>10</retryInterval>")
        self.response.out.write("<retryDuration>300</retryDuration>")
        self.response.out.write("</result>")


    def gen_random_string(self):
        #Excluding 0, O, 1, I to avoid confusion
        alphabet="ABCDEFGHJKLMNPQRSTUVWXYZ23456789"

        while True:
            string = ''.join([choice(alphabet) for i in range(4)])
            q = Registration.all()
            q.filter("reg_code =",string)
            q.filter("reg_complete =",False)
            results = q.fetch(1)

            if not len(results):
                return string

class RegResultHandler(webapp.RequestHandler):
    def get(self):
        device_id = self.request.get("deviceID")
        reg_code = self.request.get("regCode")

        q = Registration.all()
        q.filter("reg_code =",reg_code)
        q.filter("device_id =",device_id)
        results = q.fetch(1)

        if not len(results):
            self.response.out.write("<result><status>failure</status></result>")
        else:
            if results[0].reg_complete:
                self.response.out.write("<result>")
                self.response.out.write("<status>complete</status>")
                oauth_verifier=results[0].oauth_verifier
                if oauth_verifier:
                    self.response.out.write("<oauth_verifier>"+oauth_verifier+"</oauth_verifier>")
                self.response.out.write("</result>")
            else:
                self.response.out.write("<result><status>incomplete</status></result>")


class MainHandler(webapp.RequestHandler):
    def get(self):
        error=False
        complete=False
        smugmug=True
        pub_checked="checked"
        full_checked=""
        
        status = self.request.get("status")
        if status == "error":
            error=True
        elif status=="complete":
            complete=True
        
        access_type = self.request.get("accesstype", default_value="Public")
        if access_type=="Full":
            pub_checked=""
            full_checked="checked"
        
        reg_code = self.request.get("reg_code")
        service = self.request.get("service", default_value="smugmug")
        if service!="smugmug":
            smugmug = False

        template_params = {
            'complete': complete,
            'access_error': error,
            'reg_code': reg_code,
            'smugmug' : smugmug,
            'service' : service,
            'pub_checked' : pub_checked,
            'full_checked' : full_checked,
        }
        path = os.path.join(os.path.dirname(__file__), 'form.html')
        self.response.out.write(template.render(path, template_params))

class OAuthAuthorizeHandler(webapp.RequestHandler):
    def post(self):
        reg_code = self.request.get("regcode").upper()
        accesstype = self.request.get("accesstype",default_value="Public")
        service = self.request.get("service",default_value="smugmug")
        
        q = Registration.all()
        q.filter("reg_code =",reg_code)
        q.filter("reg_complete =",False)
        results = q.fetch(1)

        if not len(results):
            accesstype_str=""
            if service=="smugmug":
                accesstype_str="&accesstype="+accesstype
            self.redirect("/?status=error"+accesstype_str+"&reg_code="+reg_code+"&service="+service)
        else:
            oauth_token=results[0].oauth_token
            if results[0].service == "smugmug":
                self.redirect("http://api.smugmug.com/services/oauth/authorize.mg?Permissions=Read&Access="+accesstype+"&oauth_token="+oauth_token)
            elif results[0].service == "picasa":
                self.redirect("https://www.google.com/accounts/OAuthAuthorizeToken?oauth_token="+oauth_token)
            elif results[0].service == "flickr":
                self.redirect("http://www.flickr.com/services/oauth/authorize?oauth_token="+oauth_token+"&perms=read")

class OAuthCallbackHandler(webapp.RequestHandler):
    def get(self):
        oauth_token = self.request.get("oauth_token")
        oauth_verifier = self.request.get("oauth_verifier")

        q = Registration.all()
        q.filter("oauth_token =",oauth_token)
        q.filter("reg_complete =",False)
        results = q.fetch(1)

        if not len(results):
            self.redirect("/")
        else:
            results[0].reg_complete=True
            if oauth_verifier != "":
                results[0].oauth_verifier=oauth_verifier
            results[0].put()
            self.redirect("/?status=complete")
            
class ServiceHandler(webapp.RequestHandler):
    def get(self,service):
        service = service.lower()
        if service == "picassa":
            service = "picasa"
        self.redirect("/?service="+service)

class ArchiveHandler(webapp.RequestHandler):
    def get(self):
        hist_date = datetime.today() - timedelta(days=2)

        q = Registration.all()
        q.filter("create_time <",hist_date)
        results = q.fetch(1000)

        for i in range(len(results)):
            db.delete(results[i])

application = webapp.WSGIApplication([
    (r"/oauth/callback", OAuthCallbackHandler),
    (r"/oauth/authorize", OAuthAuthorizeHandler),
    (r"/getRegCode", RegCodeHandler),
    (r"/getRegResult", RegResultHandler),
    (r"/signup", LinkHandler),
    (r"/tasks/archive", ArchiveHandler),
    (r"/(?i)(picasa|picassa|smugmug|flickr)/*", ServiceHandler),
    (r"/", MainHandler),
])

def main():
    run_wsgi_app(application)

if __name__ == "__main__":
  main()
