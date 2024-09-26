from minet.web import request
from math import ceil
from ural import get_domain_name, urlpathsplit, is_url
from auth import COOKIE
from time import sleep
import random


def get_old_url(url):
    domain = get_domain_name(url)
    path = urlpathsplit(url)
    return f"https://old.{domain}/" + "/".join(path)


def get_new_url(url):
    domain = get_domain_name(url)
    path = urlpathsplit(url)
    return f"https://www.{domain}/" + "/".join(path)


def is_user(user):
    response = request(f"https://old.reddit.com/user/{user}")
    if response.status == 200:
        return True
    return False


def get_subreddit_url(subreddit: str):
    if subreddit.count("/") == 0:
        subreddit = f"r/{subreddit}"
    subreddit = f"https://www.reddit.com/{subreddit}"
    return subreddit


def verify_subreddit(sub_url):
    if not is_url(sub_url):
        sub_url = get_subreddit_url(sub_url)
    response = request(sub_url)
    soup = response.soup()
    verif = soup.scrape("div[class='flex flex-col justify-center']")
    return len(verif) == 0


def get_posts_urls(url, nb_post):
    list_posts = set()
    nb_pages = ceil(nb_post / 25)
    old_url = get_old_url(url)

    for _ in range(nb_pages):
        response = request(old_url, spoof_ua=True)
        soup = response.soup()
        list_buttons = soup.select("ul[class='flat-list buttons']")
        for link in list_buttons:
            if len(link.scrape("span[class='promoted-span']")) == 0:
                list_posts.update(link.scrape("a[class^='bylink comments']", "href"))
        old_url = soup.scrape("span[class='next-button'] a", "href")[0]
        sleep(random.uniform(0, 1))
    return list_posts


def get_posts(url, nb_post):
    list_posts_url = get_posts_urls(url, nb_post)
    for url in list_posts_url:
        response = request(url, spoof_ua=True)
        soup = response.soup()
        title = soup.force_select_one("a[class^='title']").get_text()
        print(title)
        upvote = soup.force_select_one("div[class='score'] span").get_text()
        print(upvote)
        author = soup.scrape_one("a[class^='author']", "href")
        print(author)
        published_date = soup.scrape_one("div[class='date'] time", "datetime")
        print(published_date)
        link = soup.scrape_one("a[class^='title']", "href")
        if urlpathsplit(link) == urlpathsplit(url):
            link = None
        print(link)
        sleep(random.uniform(0, 1))


# def get_comments(url):
#     old_url = get_old_url(url)
#     response = request(old_url, cookie=COOKIE)
#     soup = response.soup()
#     comments = soup.scrape()


# get_posts("https://www.reddit.com/r/france", 10)
