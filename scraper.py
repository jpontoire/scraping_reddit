from minet.web import request
from math import ceil
from ural import get_domain_name, urlpathsplit, is_url
from time import sleep
from type import RedditPost, RedditComment
import json
from ebbe import getpath
from collections import deque
from urllib.parse import urljoin
import csv
import re
import sys
import os

ID_RE = re.compile(r"t1_(\w+)")

# --------------------------------------------------------- TOOLS --------------------------------------------------------------------


def get_old_url(url):
    domain = get_domain_name(url)
    path = urlpathsplit(url)
    old_url = f"https://old.{domain}"
    for ele in path:
        old_url = urljoin(old_url, f"{ele}/")
    return old_url


def get_new_url(url):
    domain = get_domain_name(url)
    path = urlpathsplit(url)
    new_url = f"https://old.{domain}"
    for ele in path:
        new_url = urljoin(new_url, f"{ele}/")
    return new_url

def get_url_from_subreddit(name: str):
    if is_url(name):
        return name
    name = name.lstrip("/")
    if name.startswith("r/"):
        return urljoin("https://old.reddit.com/", name)
    return urljoin("https://old.reddit.com/r/", name)


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
    remaining_requests = float(response.headers["x-ratelimit-remaining"])
    if remaining_requests == 1:
        time_remaining = int(response.headers["x-ratelimit-reset"])
        print(f"Time before next request : {time_remaining}s")
        sleep(time_remaining)
        return reddit_request(url)
    if response.status == 429:
        return reddit_request(url)
    return response


# ------------------------------------------------------- GET POSTS --------------------------------------------------------------


def get_posts_urls(url, nb_post):
    dir_name = urlpathsplit(url)[1]
    try:
        os.mkdir(dir_name)
    except FileExistsError:
        pass
    except PermissionError:
        print(f"Permission denied: Unable to create '{dir_name}'.")
    except Exception as e:
        print(f"An error occurred: {e}")
    list_posts = set()
    nb_pages = ceil(int(nb_post) / 25)
    old_url = get_old_url(url)
    n_crawled = 0
    for _ in range(nb_pages):
        if n_crawled == int(nb_post):
            break
        response = reddit_request(old_url)
        soup = response.soup()
        list_buttons = soup.select("ul[class='flat-list buttons']")
        for link in list_buttons:
            if n_crawled == int(nb_post):
                break
            if len(link.scrape("span[class='promoted-span']")) == 0:
                list_posts.update(link.scrape("a[class^='bylink comments']", "href"))
                n_crawled += 1
        old_url = soup.scrape("span[class='next-button'] a", "href")[0]
    return list_posts


def get_posts(url, nb_post):
    posts = []
    list_posts_url = get_posts_urls(url, nb_post)
    for url in list_posts_url:
        response = reddit_request(url)
        if response.url == 429:
            print(response.headers)
            print(response.end_url)
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
        posts.append(post)
    return posts


def get_posts_info_on_subreddit(
    url, nb_posts
):  # ça permet pas de récupérer le texte de l'auteur
    list_posts = []
    nb_pages = ceil(int(nb_posts) / 25)
    old_url = get_old_url(url)
    n_crawled = 0
    for _ in range(nb_pages):
        response = reddit_request(old_url)
        soup = response.soup()
        posts = [
            post
            for post in soup.select("div[id^='thing_t3']")
            if "promotedlink" not in post.get("class", [])
        ]
        for post in posts:
            if n_crawled == nb_posts:
                break
            n_crawled += 1
            title = post.force_select_one("a[class^='title']").get_text()
            upvote = post.force_select_one("div[class='score unvoted']").get_text()
            author = post.scrape_one("a[class^='author']", "href")
            published_date = post.scrape_one("p[class='tagline'] time", "datetime")
            link = post.scrape_one("a[class^='title']", "href")
        # print(len(posts))


# ------------------------------------------------------------- JSON ----------------------------------------------------------------------------------------


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


def get_comments_json(url):
    list_return = []
    list_comments = deque()
    old_url = get_old_url(url)
    old_url_json = get_json_link(old_url)
    list_comments.append(old_url_json)
    while list_comments:
        if len(list_comments) % 2 == 0:
            urls = list_comments.popleft()
        else:
            urls = list_comments.pop()
        if len(urls) == 7 or isinstance(urls, str):
            response = reddit_request(get_json_link(get_permalink(old_url, urls)))
            json_page = json.loads(response.text())
            for comment in json_page[1]["data"]["children"]:
                data, list_comments = get_childs(comment, list_comments)
                list_return.append(data)
        else:
            data, list_comments = get_childs(urls, list_comments)
            list_return.append(data)
    return len(list_return), list_return


# ---------------------------------------------------------- Optimized version ------------------------------------------------------------------------------


def extract_t1_ids(text: str):
    ids = [match.group(1) for match in re.finditer(ID_RE, text)]
    if ids:
        return ids
    return text.split("'")[-4].split(",")


def get_childs_l500(url, list_comments, parent_id):
    response = reddit_request(url)
    soup = response.soup()
    comments = soup.select("div[class='commentarea']>div>div[class*='comment']")
    for com in comments:
        child = com.find("div", class_="child")
        if child.text != "":
            child = child.find("div")
            child_com = child.find_all(
                "div",
                class_=lambda x: x
                and (
                    "comment" in x
                    or "deleted comment" in x
                    or "morerecursion" in x
                    or "morechildren" in x
                ),
                recursive=False,
            )
            for ele in child_com:
                list_comments.append((parent_id, ele))
    return list_comments


def get_current_id(com):
    current_id = com.get("id")
    if current_id:
        current_id = current_id.split("_")[-1]
    else:
        current_id = com.get("data-permalink").split("/")[-2]
    return current_id


def get_infos_on_post(response, main_dir_name, com_dir_name):
    soup = response.soup()
    title = soup.force_select_one("a[class^='title']").get_text()
    upvote = soup.force_select_one("div[class='score'] span").get_text()
    author = soup.scrape_one("a[class^='author']", "href")
    published_date = soup.scrape_one("div[class='date'] time", "datetime")
    link = soup.scrape_one("a[class^='title']", "href")
    if urlpathsplit(link) == urlpathsplit(response.end_url):
        link = None
    author_text = soup.scrape_one(
        "div[id='siteTable'] div[class^='usertext-body'] div p"
    )
    post = RedditPost(
        title=title,
        url=response.end_url,
        author=author,
        author_text=author_text,
        upvote=upvote,
        published_date=published_date,
        link=link,
    )
    url_split = urlpathsplit(post.url)
    file_name = f"{url_split[1]}_{url_split[3]}"
    with open(f"{main_dir_name}/{com_dir_name}/{file_name}.csv", "w") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "Title",
                "URL",
                "Author",
                "Author Text",
                "Upvote",
                "Published Date",
                "Link",
            ]
        )
        writer.writerow(
            [
                post.title,
                post.url,
                post.author,
                post.author_text,
                post.upvote,
                post.published_date,
                post.link,
            ]
        )


def get_comments(url, version):
    if not (version == "all" or version == "fast"):
        print("Erreur version")
        return 0
    url_split = urlpathsplit(url)
    main_dir_name = url_split[1]
    com_dir_name = url_split[3]
    try:
        os.mkdir(f"{main_dir_name}/{com_dir_name}")
    except FileExistsError:
        pass
    except PermissionError:
        print(f"Permission denied: Unable to create '{com_dir_name}'.")
    except Exception as e:
        print(f"An error occurred: {e}")
    list_return = []
    m_comments = []
    old_url = get_old_url(url)
    url_limit = old_url + "?limit=500"
    response = reddit_request(url_limit)
    get_infos_on_post(response, main_dir_name, com_dir_name)
    soup = response.soup()
    first_comments = soup.select("div[class='commentarea']>div>div[class*='comment']")
    for ele in first_comments:
        m_comments.append((None, ele))
    while m_comments:
        parent, com = m_comments.pop()
        current_id = get_current_id(com)
        if "morerecursion" in com.get("class") and version == "all":
            url_rec = f"https://old.reddit.com{com.scrape_one("a", "href")}"
            m_comments = get_childs_l500(url_rec, m_comments, parent)
        elif "morechildren" in com.get("class") and version == "all":
            a = com.select_one("a")
            onclick = a["onclick"]
            id_list = extract_t1_ids(onclick)
            for id in id_list:
                comment_url = f"{old_url}{id}"
                m_comments = get_childs_l500(comment_url, m_comments, current_id)
        else:
            child = com.find("div", class_="child")
            if child.text != "":
                child = child.find("div")
                if version == "all":
                    child_com = child.find_all(
                        "div",
                        class_=lambda x: x
                        and (
                            "comment" in x
                            or "deleted comment" in x
                            or "morerecursion" in x
                            or "morechildren" in x
                        ),
                        recursive=False,
                    )
                else:
                    child_com = child.find_all(
                        "div",
                        class_=lambda x: x
                        and ("comment" in x or "deleted comment" in x),
                        recursive=False,
                    )
                for ele in child_com:
                    m_comments.append((current_id, ele))
            data = RedditComment(
                id=current_id,
                parent=parent,
                comment=com.scrape_one("div[class='md']:not(div.child a)"),
            )
            if data.id != "":
                list_return.append(data)
    file_name = f"{url_split[1]}_{url_split[3]}_comments"
    with open(
        f"{main_dir_name}/{com_dir_name}/{file_name}.csv",
        "w",
        newline="",
        encoding="utf-8",
    ) as file:
        writer = csv.writer(file)
        writer.writerow(["ID", "Parent", "Comment"])
        for comment in list_return:
            writer.writerow([comment.id, comment.parent, comment.comment])


def main(args):  # url - nb_posts - mode
    posts = get_posts_urls(args[0], args[1])
    i=0
    for post in posts:
        i+=1
        print(f"Post n°{i}")
        get_comments(post, args[2])
        sleep(1)


if __name__ == "__main__":
    main(sys.argv[1:])
