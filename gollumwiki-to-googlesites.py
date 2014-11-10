#!/usr/bin/python

import codecs
import getopt
import glob
import markdown
import mimetypes
import os.path
import pprint
import re
import sys

import gdata.sample_util
import gdata.sites.client
import gdata.sites.data

#------------------------------------------------------------------------------
# GollumToMarkdownLinks()
#------------------------------------------------------------------------------
def GollumToMarkdownLinks(pageName,markdown):
    result = markdown

    # First replace all [[<text>|<ref>]] with [<text>](<ref>)
    linkWithRefExpr = r'\[\[(?P<text>.*)\|(?P<ref>.*)\]\]'
    def linkWithRefFunc(match):
        #print "    [[text|ref]] MATCH:", match.groupdict()
        return "[%(text)s](%(ref)s)"%match.groupdict()
    result = re.sub(linkWithRefExpr, linkWithRefFunc, result)

    # Then replace all [[<dir>/<file>]] with ![<file>](<file>)
    linkExpr = r'\[\[(?P<dir>.*)/(?P<file>.*)\]\]'
    def linkFunc(match):
        #print "    [[dir/file]] MATCH:", match.groupdict()
        tokens = match.groupdict()
        tokens['pageName'] = pageName
        return "![%(file)s](%(pageName)s/%(file)s)"%tokens
    result = re.sub(linkExpr, linkFunc, result)
    return result

#------------------------------------------------------------------------------
# AddTableBorders()
#------------------------------------------------------------------------------
def AddTableBorders(html):
    result = re.sub(r'<table>', '''<table border="1" bordercolor="#888" cellspacing="0" style="border-collapse:collapse;border-color:rgb(136,136,136);border-width:1px">''', html)
    return result

#------------------------------------------------------------------------------
# GetHtmlFromMarkdownFile()
#------------------------------------------------------------------------------
def GetHtmlFromMarkdownFile(pageName, filename):
    # Read markdown from file
    markdownFile = codecs.open(filename, mode="r", encoding="utf-8")
    markdownText = markdownFile.read()

    # Run markdown pre-processors
    markdownText = GollumToMarkdownLinks(pageName, markdownText)

    # Convert markdown to html (this will be unicode)
    htmlUnicode = markdown.markdown(markdownText,
                                    extensions=['markdown.extensions.tables'] )
    tmpFileName = "/var/tmp/_wiki-push-tmp"
    tmpFile = codecs.open(tmpFileName, mode='w', encoding='utf-8')
    tmpFile.write(htmlUnicode)
    tmpFile.close()
    html = open(tmpFileName, "r").read()

    # Run html post-processors
    html = AddTableBorders(html)

    return html

#------------------------------------------------------------------------------
# GetSiteContentByPath()
#------------------------------------------------------------------------------
def GetSiteContentByPath(client, path):
    '''Return a specific site entry by /path/to/entry.'''
    uri = '%s?path=%s'%(client.MakeContentFeedUri(), path)
    feed = client.GetContentFeed(uri=uri)
    if not feed or not feed.entry or feed.entry < 1:
        return None
    return feed.entry[0]

#------------------------------------------------------------------------------
# PushPages()
#------------------------------------------------------------------------------
def PushPages(client, pagesDir, parentPage, domain, site):

    # Find parent page.
    # Page must exist.
    parentEntry = None
    if parentPage:
        parentEntry = GetSiteContentByPath(client, parentPage)
        if not parentEntry:
            print "Parent page not found: '%s'"%parentPage
            return

    # Create all the child pages, under parentPage
    print "Scanning", pagesDir, "..."
    mdFiles = sorted(glob.glob(os.path.join(pagesDir, "*.md")))
    for mdFile in mdFiles:
        pageName = os.path.splitext(os.path.basename(mdFile))[0]

        # skip internal pages
        if pageName.startswith('_'):
            print "Internal page", pageName, "skipping"
            continue

        print "Creating", pageName 
        title = pageName.replace('-',' ')
        html = GetHtmlFromMarkdownFile(pageName, mdFile)
        pageEntry = client.CreatePage('webpage',
                                  title,
                                  html,
                                  page_name=pageName,
                                  parent=parentEntry )

    # Print a URL for convenience.
    if parentEntry.GetAlternateLink():
        print 'Pages created at:',parentEntry.GetAlternateLink().href


#------------------------------------------------------------------------------
# GoogleSitesLogin()
# Returns a client, or None.
#------------------------------------------------------------------------------
def GoogleSitesLogin(site_name=None, site_domain=None, debug=False):
    if site_domain is None:
        raise ValueError("site_domain is not valid")
    if site_name is None:
        raise ValueError("site_name is not valid")

    mimetypes.init()

    client = gdata.sites.client.SitesClient( source="wiki-push",
                                             site=site_name,
                                             domain=site_domain )
    client.http_client.debug = debug

    try:
        gdata.sample_util.authorize_client( client,
                        auth_type=gdata.sample_util.CLIENT_LOGIN,
                        service=client.auth_service,
                        source="wiki-push",
                        scopes=['http://sites.google.com/feeds/',
                                'https://sites.google.com/feeds/'] )
    except gdata.client.BadAuthentication:
        print "Invalid user credentials given."
        return None
    except gdata.client.Error:
        print "Login Error."
        return None

    return client


#------------------------------------------------------------------------------
# main()
#------------------------------------------------------------------------------
def main():
    debug = False
    domain = None
    site = None
    parentPage = None

    usage = '''
gollumwiki-to-googlesites [<options>] <pagesDir/>
Options:
         --debug

         --domain <domainName>  (required)
         --site <siteName>      (required)

         --email <login>
         --password <password>

         --parent-page </path/to/parent> (page must already exist)
'''

    # Parse args
    try:
        opts, args = getopt.getopt(sys.argv[1:], '',
                                    ['debug',
                                     'domain=',
                                     'site=',
                                     'email=',
                                     'password=',
                                     'parent-page='])
    except getopt.error, msg:
        print usage
        sys.exit(2)

    if len(args) != 1:
        print "Must specified directory containing pages."
        print usage
        sys.exit(3)

    for option, arg in opts:
        if option == '--debug':
            debug = True
        elif option == '--domain':
            domain = arg
        elif option == '--site':
            site = arg
        elif option == '--parent-page':
            parentPage = arg

    if not domain or not site:
        print "Must specify domain and site names."
        print usage
        sys.exit(4)

    # Remove trailing slash from pagesDir
    pagesDir = args[0].rstrip('/')

    # Login in to google sites
    client = GoogleSitesLogin(site, domain, debug)
    if not client:
        sys.exit(5)

    # Push content pages
    PushPages(client, pagesDir, parentPage, domain, site)

if __name__ == '__main__':
  main()

# End
