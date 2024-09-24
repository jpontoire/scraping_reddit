from minet.web import request
from math import ceil
from ural import get_domain_name, urlpathsplit
from auth import COOKIE

def get_old_url(url):
    domain = get_domain_name(url)
    path = urlpathsplit(url)
    return f"https://old.{domain}/" + "/".join(path)


def get_posts(url, nb_post):
    list_posts = set()
    nb_pages = ceil(nb_post/25)
    old_url = get_old_url(url)

    for _ in range(nb_pages):
        print(old_url)
        response = request(old_url, cookie=COOKIE
        posts = soup.scrape("a[class^='bylink comments']", "href")
        list_posts.update(posts)
        old_url = soup.scrape("span[class='next-button'] a", "href")[0]
    print(list_posts)




get_posts("https://www.reddit.com/r/france", 50)
