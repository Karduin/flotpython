import logging

logging.basicConfig(filename='diagnose.log', filemode='w',
                    level=logging.WARNING)
# logging.basicConfig(level=logging.DEBUG)
import urllib2
import time
from operator import itemgetter

# helper function
def extract_domains_from_url(url):
    """
    Extract a domain from the URL

    Return a tuple T containing
    T[0]: domain with the correct URL (http://domain or https://domain)
    T[1]: domain only without the propocol (http or https)
    """
    protocol_http = 'http://' 
    protocol_https = 'https://' 
    protocol = ''
    if url.startswith(protocol_http):
        url = url.replace(protocol_http, '')
        protocol = protocol_http
    elif url.startswith(protocol_https):
        url = url.replace(protocol_https, '')
        protocol = protocol_https
    else:
        logging.debug('Extract domain error: ' + url)
        return ''
    domain = url[:url.find('/')]
    return (protocol + domain, domain)

class HTMLPage(object):
    """
    represent a HTML Web page. The constructor takes a URL and
    contruct the HTMLPage object

    The object has 3 attributes:
        -url: the URL that corresponds to the Web page
        -html_it: an iterator that interates on the raw HTML code of 
          the page, one line at a time
        -urls: the list of all URLs contained in the HTML page
        -http_code: the code return by HTTP while accessing the page, 
         un http_code=0 means a URL error (not an HTTP error)
    """

    def __init__(self, url):
        self.http_code = 0
        self.url = url
        self.html_it = self.page_fetcher(self.url)
        self.urls = self.extract_urls_from_page()

    def page_fetcher(self, url):
        """
        open the HTML page and return the object that gives access to
        this page
        """
        try:
            page = urllib2.urlopen(url)
            self.http_code = page.getcode()
            return page
        except urllib2.HTTPError as e:
            logging.warning('HTTPError: cannot open {}. Reason {}, code {}'
                            .format(url, e.reason, e.code))
            self.http_code = e.code
            return []

        except urllib2.URLError as e:
            logging.warning('URLError: cannot open {}. Reason {}'
                            .format(url, e.reason))
            return []

    def extract_urls_from_page(self):
        """
        Build a list of URLs contained in the body of an HTML page.

        The parsing is basic, I just extract URLs in href fields I
        return a list of unique URLs.
        """

        # parse the page to extract all URLs in href field and in the
        # body of the document
        list_urls = []
        is_body = False
        for line in self.html_it:
            # line = line.lower()
            if is_body:
                if "href=" in line.lower():
                    # extract everything between href=" and "> probably
                    # not bullet proof, but should work most of the
                    # time
                    url_separator = line[line.lower().find('href=') + 5]
                    line = line[line.lower().find('href=') + 6:]
                    line = line[:line.lower().find(url_separator)]
                    list_urls.append(line)
                elif "http://" in line:
                    logging.debug('this URL was not extracted: ' + line)
            else:
                if '<body>' in line:
                    is_body = True

        # keep only http and https
        filtered_list_urls = [x for x in list_urls
                              if x.lower().startswith('http')
                              or x.lower().startswith('https')]
        # and reconstruct relative links ./
        filtered_list_urls.extend([self.url[:self.url.rfind('/')] + x[1:]
                                   for x in list_urls
                                   if x.startswith('./')])

        # and reconstruct relative links /
        filtered_list_urls.extend([extract_domains_from_url(self.url)[0] 
                                   + x[1:] for x in list_urls
                                   if x.startswith('./')])
        # debug
        # print [x for x in list_urls if x.startswith('./')]

        return list(set(filtered_list_urls))


class Crawler(object):
    """
    This object that will manage the crawl of the pages. To get URLs
    this objet must be used as an iterator. Each step will return a
    new page to be crawled.

    The constructor accept a 
    -seed_url: the URL from which the crawl is starting
    -max_crawled_sites: the maximum number of crawled sites
     (10**100 by default)
    -domain_filter: the list of domains the crawled must stay in 
     (no filter by default)
    """

    def __init__(self, seed_url, max_crawled_sites=10 ** 100,
                 domain_filter=None):
        if domain_filter is None:
            domain_filter = []
        self.seed_url = seed_url
        # Each key is a URL, and the value for url1 is the list of
        # sites that referenced url1
        self.sites_to_be_crawled_dict = {}

        # set of the sites still to be crawled
        self.sites_to_be_crawled = set([])
        self.domains_to_be_crawled = set([])

        # set of the sites already crawled
        self.sites_crawled = set([])
        self.domains_crawled = set([])

        self.domain_filter = domain_filter
        # crawling time contains the list of the crawl time for each
        # page
        # crawling_time = []

        self.max_crawled_sites = max_crawled_sites

        #duration of the last crawl
        self.last_crawl_duration = 0

    def update_sites_to_be_crawled(self, page):
        """
        get an HTMLpage object as argument, retreive all urls from
        this object and update the dict sites_to_be_crawled_dict and
        the sets sites_to_be_crawled and domains_to_be_crawled
        """
        for url in page.urls:
            # if there is no domain in the filter, always pass the
            # filter
            if self.domain_filter:
                pass_filter = False
            else:
                pass_filter = True

            extracted_domain = extract_domains_from_url(url)[1]
            for domain in self.domain_filter:
                if domain in extracted_domain:
                    pass_filter = True

            if pass_filter:
                # update the dict even if url already crawled (to get
                # comprehensif information)
                if url in self.sites_to_be_crawled_dict:
                    self.sites_to_be_crawled_dict[url].append(page.url)
                else:
                    self.sites_to_be_crawled_dict[url] = [page.url]

                # update the set if url not already crawled
                if url not in self.sites_crawled:
                    self.sites_to_be_crawled.add(url)

                self.domains_to_be_crawled.add(extracted_domain)

    def __repr__(self):
        output = ('#' * 60 + '\nInitial URL: {}'.format(self.seed_url)
                   + '\nSites/domains already crawled {}/{}'.format(
                 len(self.sites_crawled),
                 len(self.domains_crawled))
                   + '\nSites/domains to be crawled {}/{}'.format(
                 len(self.sites_to_be_crawled),
                 len(self.domains_to_be_crawled))
                   + '\n crawl duration {}'.format(
                 self.last_crawl_duration)
                  )
        return output

    def crawl_stats(self):
        """
        returns a tuple T containing current statistics on the crawl
        
        T[0]: crawled sites
        T[1]: crawled domains
        T[2]: sites to be crawled
        T[3]: domains to be crawled
        """
        return (self.sites_crawled, self.domains_crawled,
                self.sites_to_be_crawled, self.domains_to_be_crawled)

    def __iter__(self):
        """
        iterator that returns at each step a new web page that has
        been crawled
        """

        # case of the first page
        start_time = time.time()
        page = HTMLPage(self.seed_url)
        self.sites_crawled.add(seed_url)
        self.domains_crawled.add(extract_domains_from_url(seed_url)[1])
        self.update_sites_to_be_crawled(page)
        self.last_crawl_duration = time.time() - start_time
        yield page 
        
        # all the other pages
        while (self.sites_to_be_crawled and
                       len(self.sites_crawled) < self.max_crawled_sites):
            start_time = time.time()
            url = self.sites_to_be_crawled.pop()
            page = HTMLPage(url)
            self.sites_crawled.add(url)
            self.domains_crawled.add(extract_domains_from_url(url)[1])
            self.update_sites_to_be_crawled(page)
            self.last_crawl_duration = time.time() - start_time
            yield page
        raise StopIteration



# let's start the crawler
seed_url = 'http://www-sop.inria.fr/members/Arnaud.Legout/'
s = raw_input('Enter a seed URL (default to {})'.format(seed_url))

if not s:
    s = seed_url

# Let's answer funny questions in a few lines of code

####################################################
# 1) what are the less responsive sites in my domain and the dead URLs

# start the crawler restricted to a given domain
crawl = Crawler(seed_url, domain_filter=['inria'])
pages_responsivness = []
dead_urls = []
for page in crawl:
    # just to see progress on the terminal
    print crawl
    print page.http_code, page.url


    pages_responsivness.append((crawl.last_crawl_duration, page.url))

    if page.http_code != 200:
        dead_urls.append((page.http_code, page.url))

pages_responsivness.sort(key=itemgetter(0))

# now display the result
for line in pages_responsivness:
    print line

for url in dead_urls:
    print url
    if url[0] == 404:
        for site in crawl.sites_to_be_crawled_dict[url[1]]:
            print site 
        print '-'*60

logging.shutdown()