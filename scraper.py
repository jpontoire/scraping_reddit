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
import csv
import re


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


def reddit_request(url):
    response = request(url)
    remaining_requests = float(response.headers['x-ratelimit-remaining'])
    if remaining_requests == 0:
        time_remaining = int(response.headers['x-ratelimit-reset'])
        print(f"Time before next request : {time_remaining}s")
        sleep(time_remaining)
        return reddit_request(url)
    return response


def get_posts_urls(url, nb_post):
    list_posts = set()
    nb_pages = ceil(nb_post / 25)
    old_url = get_old_url(url)
    n_crawled = 0

    for _ in range(nb_pages):
        response = reddit_request(old_url)
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
        response = reddit_request(url)
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


# version avec plein de requêtes

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



# version avec moins de requêtes

def get_comments_test(url, list_return):
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
            sleep(random.uniform(1, 3))
        else:
            print("42")
            data, list_comments = get_childs(urls, list_comments)
            list_return.append(data)
    return list_return



def extract_t1_ids(text):
    pattern = r't1_(\w+)'
    return [match.group(1) for match in re.finditer(pattern, text)]


def get_comment_l500(url):
    list_return = []
    old_url = get_old_url(url)
    url_limit = old_url + "?limit=500"
    response = reddit_request(url_limit)
    soup = response.soup()
    m_comments = soup.select("div[class='commentarea']>div>div[id^='thing_t1']")
    i = 0
    verif = True
    while m_comments:
        i += 1
        print(i)
        com = m_comments.pop()
        if "morerecursion" in com.get('class'): # le délire des threads, à vérifier
            print("On est dans un thread zebi !")
            # print(com)
            # url_rec = f"https://old.reddit.com{com.scrape_one("a", "href")}"
            # print(url_rec)
            # list_return = get_comments_test(url_rec, list_return)
        elif "morechildren" in com.get('class'):
            print("Là c'est le bouton chiant")
            a = com.select_one("a")
            onclick = a['onclick']
            id_list = extract_t1_ids(onclick)
            i = 0
            for id in id_list:
                i+=1
                print(i)
                comment_url = f"{old_url}{id}"
                response = reddit_request(comment_url)
                print(f"x-ratelimit-remaining : {response.headers['x-ratelimit-remaining']}")
                print(f"time before reset : {response.headers['x-ratelimit-reset']}")
                soup = response.soup()
                comments = soup.select("div[class='commentarea']>div>div[id^='thing_t1']")
                for com in comments:
                    m_comments.append(com)
                
        else:
            child = com.find('div', class_='child')
            if child.text != "":
                child = child.find('div')
                child = child.find_all('div', id=lambda x: x and x.startswith('thing_t1'), recursive=False)
                for ele in child:
                    m_comments.append(ele)
                    if "morerecursion" in ele.get('class'):
                        verif = False
            if verif:
                data = RedditComment(
                    id=com.get('id').split('_')[-1],
                    parent="test",
                    comment=com.scrape_one("div[class='md']:not(div.child a)")
                )
                if data.id != "":
                    list_return.append(data)
            verif = True
    with open("test.csv", "w", newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(["ID", "Parent", "Comment"])
        for comment in list_return:
            writer.writerow([comment.id, comment.parent, comment.comment])




# get_comment_l500("https://old.reddit.com/r/france/comments/1fvtx1f/%C3%A0_paris_le_parc_locatif_seffondre_car_des/")

# get_comment_l500("https://old.reddit.com/r/AskReddit/comments/1g0ewi1/what_makes_you_lonely/")

get_comment_l500("https://old.reddit.com/r/reddit/comments/1css0ws/we_heard_you_awards_are_back/?limit=500")