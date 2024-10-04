from minet.web import request
from math import ceil
from ural import get_domain_name, urlpathsplit, is_url
from auth import COOKIE
from time import sleep
import random
from type import RedditPost, RedditComment
import json
from ebbe import getpath
from collections import deque
from urllib.parse import urljoin


def get_old_url(url):
    domain = get_domain_name(url)
    path = urlpathsplit(url)
    return f"https://old.{domain}/" + "/".join(path) + "/"


def get_new_url(url):
    domain = get_domain_name(url)
    path = urlpathsplit(url)
    return f"https://www.{domain}/" + "/".join(path) + "/"


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


def has_reddit_comments(url):
    url = get_old_url(url)
    response = request(url)
    soup = response.soup()
    no_comments = soup.scrape_one("p[id='noresults']")
    if no_comments == "there doesn't seem to be anything here":
        return False
    return True


def get_posts_urls(url, nb_post):
    list_posts = set()
    nb_pages = ceil(nb_post / 25)
    old_url = get_old_url(url)
    n_crawled = 0

    for _ in range(nb_pages):
        response = request(old_url, spoof_ua=True)
        soup = response.soup()
        list_buttons = soup.select("ul[class='flat-list buttons']")
        for link in list_buttons:
            if n_crawled == nb_post:
                break
            if len(link.scrape("span[class='promoted-span']")) == 0:
                list_posts.update(link.scrape("a[class^='bylink comments']", "href"))
                n_crawled += 1
        old_url = soup.scrape("span[class='next-button'] a", "href")[0]
        sleep(random.uniform(0, 1))
    return list_posts


def get_posts(url, nb_post):
    posts = []
    list_posts_url = get_posts_urls(url, nb_post)
    for url in list_posts_url:
        response = request(url, spoof_ua=True)
        soup = response.soup()
        title = soup.force_select_one("a[class^='title']").get_text()
        upvote = soup.force_select_one("div[class='score'] span").get_text()
        author = soup.scrape_one("a[class^='author']", "href")
        published_date = soup.scrape_one("div[class='date'] time", "datetime")
        link = soup.scrape_one("a[class^='title']", "href")
        if urlpathsplit(link) == urlpathsplit(url):
            link = None
        author_text = soup.scrape_one(
            "div[id='siteTable'] div[class^='usertext-body'] div p"
        )
        post = RedditPost(
            title=title,
            url=url,
            author=author,
            author_text=author_text,
            upvote=upvote,
            published_date=published_date,
            link=link,
        )
        print(post)
        posts.append(post)
        sleep(random.uniform(0, 1))
    return posts


def get_permalink(url, id):
    if is_url(id):
        return id
    return urljoin(url, id) + "/"


def get_json_link(url):
    return urljoin(url, ".json")


def get_childs(comment, list_comments: list):
    if comment["kind"] == "more":
        for child in getpath(comment, ["data", "children"]):
            list_comments.append(child)
    else:
        if getpath(comment, ["data", "replies"]) != "":
            replies = getpath(comment, ["data", "replies", "data", "children"])
            for replie in replies:
                if replie["kind"] == "more":
                    for ele in getpath(replie, ["data", "children"]):
                        list_comments.append(ele)
                else:
                    list_comments.append(replie)
    data = RedditComment(
        id=getpath(comment, ["data", "name"]),
        parent=getpath(comment, ["data", "parent_id"]),
        comment=getpath(comment, ["data", "body"]),
    )
    return data, list_comments


def get_comments(url):
    list_return = []
    list_comments = deque()
    old_url = get_old_url(url)
    old_url_json = get_json_link(old_url)
    list_comments.append(old_url_json)
    while list_comments:
        if len(list_comments)%2 == 0:
            urls = list_comments.popleft()
        else:
            urls = list_comments.pop()
        if len(urls) == 7 or isinstance(urls, str):
            response = request(get_json_link(get_permalink(old_url, urls)))
            print(response.status)
            while(response.status == 429):
                sleep(120)
                response = request(get_json_link(get_permalink(old_url, urls)))
                print(response.status)
            json_page = json.loads(response.text())
            for comment in json_page[1]["data"]["children"]:
                data, list_comments = get_childs(comment, list_comments)
                list_return.append(data)
            sleep(random.uniform(0, 1))
        else:
            print("42")
            data, list_comments = get_childs(urls, list_comments)
            list_return.append(data)
    return len(list_return), list_return



def get_comment_l500(url):
    list_return = []
    list_comments = deque()
    old_url = get_old_url(url) + "?limit=500"
    response = request(old_url, spoof_ua=True)
    soup = response.soup()
    m_comments = soup.select("div[class='commentarea']>div>div[id^='thing_t1']")
    i = 0
    while m_comments:
        i += 1
        print(i)
        com = m_comments.pop()
        # print(com.get_display_text())
        # n_childs = com.scrape_one("a[class='numchildren']:not(div.child a)")
        # n_childs = com.find('a', class_='numchildren').text
        # print(n_childs)
        # if int(n_childs[1]) > 0:
        child = com.find('div', class_='child')
        if child.text != "":
            print(child)
            child = child.find('div')
            child = child.find_all('div', id=lambda x: x and x.startswith('thing_t1'), recursive=False)
            # print(child)
            for ele in child:
                m_comments.append(ele)
        data = RedditComment(
            id="test",
            parent="test",
            comment=com.scrape_one("div[class='md']:not(div.child a)")
        )
        list_return.append(data)
    print(len(list_return))




get_comment_l500("https://old.reddit.com/r/france/comments/1fvtx1f/%C3%A0_paris_le_parc_locatif_seffondre_car_des/")



# l, p = get_comments(
#     "https://old.reddit.com/r/france/comments/1fvtx1f/%C3%A0_paris_le_parc_locatif_seffondre_car_des/",
#     "top"
# )
# print(l)
# for ele in p:
#     print(ele)
