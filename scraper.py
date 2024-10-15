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

def extract_t1_ids(text):
    pattern = r't1_(\w+)'
    return [match.group(1) for match in re.finditer(pattern, text)]


def get_childs_l500(url, list_comments):
    response = reddit_request(url)
    soup = response.soup()
    comments = soup.select("div[class='commentarea']>div>div[id^='thing_t1']")
    for com in comments:
        list_comments.append(com)
    del_comments = soup.select("div[class='commentarea']>div>div[class$='deleted comment ']")
    for com in del_comments:
        list_comments.append(com)
    return list_comments


def get_comment_l500(url):
    list_return = []
    old_url = get_old_url(url)
    url_limit = old_url + "?limit=500"
    response = reddit_request(url_limit)
    soup = response.soup()
    m_comments = soup.select("div[class='commentarea']>div>div[id^='thing_t1']")
    del_comments = soup.select("div[class='commentarea']>div>div[class$='deleted comment ']")
    for com in del_comments:
        m_comments.append(com)
    # i = 0
    verif = True
    while m_comments:
        # i += 1
        # print(i)
        com = m_comments.pop()
        if "morerecursion" in com.get('class'):
            url_rec = f"https://old.reddit.com{com.scrape_one("a", "href")}"
            m_comments = get_childs_l500(url_rec, m_comments)
        elif "morechildren" in com.get('class'):
            a = com.select_one("a")
            onclick = a['onclick']
            id_list = extract_t1_ids(onclick)
            for id in id_list:
                comment_url = f"{old_url}{id}"
                m_comments = get_childs_l500(comment_url, m_comments)
        else:
            child = com.find('div', class_='child')
            if child.text != "":
                child = child.find('div')
                child_com = child.find_all('div', id=lambda x: x and x.startswith('thing_t1'), recursive=False)
                for ele in child_com:
                    m_comments.append(ele)
                    if "morerecursion" in ele.get('class'):
                        verif = False
                child_del = child.find_all('div', class_=lambda x: x and 'deleted comment' in x, recursive=False)
                for ele in child_del:
                    m_comments.append(ele)
                    if "morerecursion" in ele.get('class'):
                        verif = False
            if verif:
                if "deleted comment" in com.get('class'):
                    data = RedditComment(
                        id=com.get('data-permalink').split('/')[-2],
                        parent="test",
                        comment='Removed'
                    )
                else:    
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
    print(len(list_return))



# get_comment_l500("https://old.reddit.com/r/mildlyinteresting/comments/1g3wrla/i_got_bit_by_a_mosquito_twice_and_a_line_joining/")

# get_comment_l500("https://old.reddit.com/r/france/comments/1g3pyan/the_understudied_female_sexual_predator/")

get_comment_l500("https://old.reddit.com/r/reddit/comments/14gb7xy/changelog_chat_and_flair_navigation_updates/?limit=500")