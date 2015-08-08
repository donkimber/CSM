
import sys, time, datetime, traceback, mailbox, os
import email.utils
from email.header import decode_header
sys.stdout = sys.stderr


HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
</head>
<body>
<h2>%(subject)s</h2>
%(body)s
</body>
</html>
"""

TXT_TEMPLATE = """%(subject)s

%(body)s
"""

HTML_HEAD = """<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
</head>
<body>
"""

HTML_FOOT = """
</body>
</html>
"""

POST_TEMPLATE = """
<a href=%(msgUrl)s>%(key)s</a> %(dateStr)s<br>
<a href="%(htmlUrl)s">%(subject)s</a>
%(author)s<br>\n"""

def getDate(date):
    if not date:
        return date
    date_tuple=email.utils.parsedate_tz(date)
    if date_tuple:
        date=datetime.datetime.fromtimestamp(email.utils.mktime_tz(date_tuple))
    ds = date.strftime("%A %Y/%m/%d %H:%M:%S %z")
    return ds

def getRefs(str):
    if str:
        str = str.replace("><", "> <").split()
    return str

def getAuthor(str):
    i = str.find("<")
    if i >= 0:
        j = str.find(">")
        str = str[:i]+str[j+1:]
    return str.strip()

def htmlSafe(s):
    s = str(s)
    s = s.replace("<", "")
    s = s.replace(">", "")
    return s

class MailParser:
    def __init__(self, name, mboxDir):
        self.mboxDir = mboxDir
        mboxPath = os.path.join(mboxDir, "%s.mbox" % name)
        self.filesDir = os.path.join(mboxDir, "files")
        t0 = time.time()
        self.mboxPath = mboxPath
        self.mbox = mailbox.mbox(mboxPath)
        self.contentTypes = {}
        self.subjects = {}
        self.authors = {}
        self.recipients = {}
        #self.msgById = {}
        self.postsByKey = {}
        self.keyById = {}
        t1 = time.time()
        if not os.path.exists(self.filesDir):
            os.mkdir(self.filesDir)
        print "Parser created in %.3fsecs" % (t1-t0)

    def scan(self, maxNum=0):
        t0 = time.time()
        n = 0
        for key in self.mbox.keys():
            if maxNum and n > maxNum:
                return
            n += 1
            try:
                self.process(key)
            except:
                print "Failed on", key
                traceback.print_exc()
        t1 = time.time()
        print "scanned in %.3fsecs" % (t1-t0)

    def process(self, key):
        #print key
        msg = self.mbox[key]
        post = {'key': key, 'refs': [], 'children': []}
        self.postsByKey[key] = post
        msgPath = os.path.join(self.filesDir, "%d.msg" % key)
        file(msgPath, "w").write(msg.as_string())
        post['msgUrl'] = "files/%d.msg" % key
        try:
            mcType = msg['Content-Type']
        except:
            print "No Content Type"
            return
        msgId = msg['Message-Id']
        self.keyById[msgId] = key
        post['msgId'] = msgId
        #self.msgById[msgId] = msg
        #self.postsByKey[msgId] = post
        try:
            refs = getRefs(msg['References'])
            if refs:
                #print "refs:", refs
                for ref in refs:
                    try:
                        rkey = self.keyById[ref]
                        post['refs'].append(rkey)
                        rpost = self.postsByKey[rkey]
                        rpost['children'].append(key)
                    except KeyError:
                        print "No key for ref", ref
        except:
            traceback.print_exc()
            print "*** problem with refs"
        subject = msg['Subject']
        subject = decode_header(subject)[0][0]
        self.subjects[key] = subject
        author = msg['From']
        self.authors[key] = author
        recipient = msg['To']
        self.recipients[recipient] = 1
        date = msg['Date']
        date = getDate(date)
        post['date'] = date
        post['author'] = author
        post['subject'] = subject
        path = str(key)
        parts = {}
        self.traverseParts(path, key, post, subject, msg, parts)
        if "text/html" in parts:
            url = self.saveAsHTML(key, parts['text/html'], subject)
            post['url'] = url
        elif "text/plain" in parts:
            url = self.saveAsTXT(key, parts['text/plain'], subject)
            post['url'] = url
            print "*** Using text/plain as HTML for", key
        else:
            print "No HTML saved for", key

    def saveAsHTML(self, key, part, subject):
        path = os.path.join(self.filesDir, "%s.html" % key)
        #print "writing", path
        body = part.get_payload(decode=True)
        vals = {'body': body,
                'subject': subject}
        htmlStr = HTML_TEMPLATE % vals
        file(path, "w").write(htmlStr)
        return "files/%s.html" % key

    def saveAsTXT(self, key, part, subject):
        path = os.path.join(self.filesDir, "%s.txt" % key)
        #print "writing", path
        body = part.get_payload(decode=True)
        vals = {'body': body,
                'subject': subject}
        htmlStr = TXT_TEMPLATE % vals
        file(path, "w").write(htmlStr)
        return "files/%s.txt" % key
        
    def traverseParts(self, path, key, post, subject, part, parts):
        try:
            cType = part['Content-Type']
        except:
            cType = "TYPE-UNKNOWN"
            print "type(part):", type(part)
            #print part
        #print "traverseParts", path, cType
        if part.is_multipart():
            i = 0
            for cpart in part.get_payload():
                i += 1
                path += ".%d" % i
                self.traverseParts(path, key, post, subject, cpart, parts)
            return
        if cType.find("text/html") >= 0:
            parts["text/html"] = part
        elif cType.find("text/plain") >= 0:
            parts["text/plain"] = part

    def writeIndex(self):
        t0 = time.time()
        f = file(os.path.join(self.mboxDir, "index.html"), "w")
        f.write(HTML_HEAD)
        f.write("<h1>Index of CSM posts</h1>\n")
        for key in self.roots:
            post = self.postsByKey[key]
            self.writePost(f, post)
        f.write(HTML_FOOT)
        t1 = time.time()
        print "wrote index in %.3fsecs" % (t1-t0)

    def writePost(self, f, post, indent=""):
        key = post['key']
        print indent+"writePost", key
        author = post['author']
        subject = post['subject']
        dateStr = post['date']
        print key, author
        print subject
        if 'url' not in post:
            print "*** skipping %s because no URL" % key
            return
        vals = {'author': getAuthor(author),
                'dateStr': dateStr,
                'msgUrl': "%s" % post['msgUrl'],
                'htmlUrl': "%s" % post['url'],
                'subject': subject, 'key': key}
        str = POST_TEMPLATE % vals
        f.write(str)
        if post["refs"]:
            f.write("Refs: %s<br>\n" % (htmlSafe(post["refs"]),))
        if post["children"]:
            f.write("Children: %s<br>\n" % (htmlSafe(post['children']),))
        if 'group' in post:
            group = post['group']
            print "group:", group
            f.write("<ul>\n")
            for gkey in group:
                post = self.postsByKey[gkey]
                self.writePost(f, post, "  ")
            f.write("</ul>\n")

    def getGraph(self, post, graph=None):
        key = post['key']
        #print "getGraph", key
        if graph == None:
            graph = dict()
        else:
            graph[key] = post['children']
        for childKey in post['children']:
            try:
                child = self.postsByKey[childKey]
            except KeyError:
                print "*** no post for key", childKey
                continue
            self.getGraph(child, graph)
        return graph
        
    def group(self):
        self.roots = []
        posts = self.postsByKey
        for key in posts:
            post = posts[key]
            if not post['refs']:
                self.roots.append(key)
        print "roots:\n", self.roots, "\n"
        for key in self.roots:
            post = self.postsByKey[key]
            if post['children']:
                post['group'] = self.getGraph(post)

    def dump(self):
        #print key, msg.keys()
        print self.contentTypes
        print "Recipients:"
        print self.recipients

if __name__ == '__main__':
    mboxDir = "C:/kimber/CSM"
    mp = MailParser("CSM", mboxDir)
    mp.scan(100)
    #mp.scan()
    print "-"*60
    #mp.process(29)
    mp.group()
    print "-"*60
    #mp.writeIndex()
    print "-"*60
    mp.writeDigest()
    print "-"*60
    mp.dump()



