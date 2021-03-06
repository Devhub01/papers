# DATABASE STUFF
###############################
##################
############

from papersite import app
from flask import g
import papersite.config
import sqlite3


def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(papersite.config.DATABASE)
        db.row_factory = dict_factory
    return db


def query_db(query, args=(), one=False):
    cur = get_db().execute(query, args)
    rv = cur.fetchall()
    cur.close()
    return (rv[0] if rv else None) if one else rv


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

# fancy sqlrow -> dict converter


def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d


def get_authors(paperid):
    return query_db("select                                      \
                        a.authorid, a.fullname                   \
                      from                                       \
                        papers_authors as pa,                    \
                        authors as a                             \
                      where                                      \
                           pa.authorid = a.authorid and          \
                           pa.paperid = ?",
                    [paperid])


def get_domains(paperid):
    return query_db("select                                      \
                        d.domainid, d.domainname from            \
                        domains as d, papers_domains as pd       \
                      where                                      \
                        pd.domainid = d.domainid and             \
                        pd.paperid = ?",
                    [paperid])


def get_keywords(paperid):
    return query_db("select                                      \
                         k.keywordid, k.keyword                  \
                       from keywords as k, papers_keywords as pk \
                       where                                     \
                         pk.keywordid = k.keywordid and          \
                         pk.paperid = ?",
                    [paperid])


def get_comment(commentid):
    return query_db("select c.commentid, c.comment, c.createtime, \
                            u.username,  c.userid, c.paperid      \
                          from                                    \
                               comments as c,                     \
                               users as u                         \
                          where c.userid = u.userid and           \
                                c.commentid = ?                   \
    ", [commentid], one=True)


def get_comments(paperid):
    return query_db("select                                      \
                          c.commentid, c.comment, c.userid,      \
                          c.createtime, c.edited_at,             \
                          e.username as edituser,                \
                          u.username                             \
                          from                                   \
                               comments as c                     \
                               left join users as u on c.userid = u.userid  \
                               left join users as e on c.edited_by = e.userid \
                          where                                  \
                                c.deleted_at is null and         \
                                c.paperid = ?                    \
                          order by c.createtime                  \
                          ",
                    [paperid])


def delete_comment(commentid):
    con = get_db()
    with con:
        con.execute('update comments set deleted_at = datetime() \
                     where commentid = ?', [commentid])
    return id


def delete_paper(paperid):
    con = get_db()
    with con:
        con.execute('update papers set deleted_at = datetime() \
                     where paperid = ?', [paperid])
    return id


def get_review(paperid):
    return query_db("select                                      \
                          r.reviewid, r.review, r.userid,        \
                                           r.createtime,         \
                          u.username                             \
                          from                                   \
                               reviews as r,                     \
                               users as u                        \
                          where r.userid = u.userid and          \
                                r.paperid = ?                    \
                          order by r.createtime desc             \
                          limit 1                                \
                          ",
                    [paperid], one=True)

# If there is no such keyword/author/domain in db,
# we will insert in into db


def get_insert_keyword(keyword):
    con = get_db()
    with con:
        con.execute("INSERT OR IGNORE INTO keywords(keyword)     \
                     VALUES(?)", [keyword])
        id = con.execute("SELECT keywordid FROM keywords         \
                          WHERE keyword = ?",
                         [keyword]).fetchone()['keywordid']
    return id


def get_insert_author(fullname):
    con = get_db()
    with con:
        con.execute("INSERT OR IGNORE INTO authors(fullname)      \
                     VALUES(?)", [fullname])
        id = con.execute("SELECT authorid FROM authors            \
                     WHERE fullname = ?",
                         [fullname]).fetchone()['authorid']
    return id


#### Updated to check domain existence in DB 
def get_insert_domain(domainname):
    con = get_db()
    with con:
        con.execute("INSERT OR IGNORE INTO domains(domainname)    \
                    SELECT (?) WHERE not exists                     \
                    (select (?) from domains where domainname = (?) COLLATE NOCASE)",(domainname,domainname,domainname))

        id = con.execute("SELECT domainid FROM domains            \
                     WHERE domainname = (?) COLLATE NOCASE",
                         [domainname]).fetchone()['domainid']
    return id
 

def likes(paperid):
    return query_db(
        "select count(*) as c                   \
        from likes                              \
        where paperid=?",
        [paperid],
        one=True)['c']


def liked_by(paperid):
    return query_db(
        "select u.username as username          \
        from likes as l, users as u             \
        where l.userid = u.userid and           \
        l.paperid=?",
        [paperid])


def get_notifs(userid=1, limit=10):
    return query_db(
        "select *                  \
         from notifs as n          \
         where n.userid = ?        \
         order by createtime desc  \
         limit ?                   \
        ",
        [userid, limit])


def get_uploader(paperid):
    return query_db(
        "select u.*                     \
     from users as u, papers as p   \
     where u.userid = p.userid      \
     and p.paperid = ?",
        [paperid], one=True)


def get_paper_w_uploader(paperid):
    return query_db("select p.*, u.username                      \
                           from papers as p,                     \
                                users as u                       \
                          where                                  \
                                p.userid   = u.userid   and      \
                                p.paperid = ?",
                    [paperid], one=True)


def histore_paper_info(paper):
    con = get_db()
    with con:
        paperid = paper['paperid']
        authors = ', '.join([a['fullname'] for a in get_authors(paperid)])
        domains = ', '.join([d['domainname'] for d in get_domains(paperid)])
        tags = ', '.join([k['keyword'] for k in get_keywords(paperid)])
        con.execute('insert into papers_history (paperid,     \
                                                 old_getlink, \
                                                 old_title,   \
                                                 old_authors, \
                                                 old_domains, \
                                                 old_tags,    \
                                                 old_edited_by, \
                                                 old_edited_at  \
                                                )               \
                                       values   (?, ?, ?, ?, ?, ?, ?, ?)',
                    [paper['paperid'],
                     paper['getlink'],
                     paper['title'],
                     authors,
                     domains,
                     tags,
                     paper['edited_by'],
                     paper['edited_at']
                     ]
                    )


############ Modifications by Devhub01 ############### 
def delete_domain(domainname):
    con = get_db()
    with con:
        con.execute('delete from domains WHERE domainname = ? \
         and domainid not in (SELECT DISTINCT domainid FROM papers_domains)', [domainname])
    return id


def delete_author(fullname):
    con = get_db()
    with con:
        con.execute('delete from authors \
                     where fullname = ?', [fullname])
    return id


def delete_tag(keyword):
    con = get_db()
    with con:
        con.execute('delete from keywords \
                     where keyword = ?', [keyword])
    return id


def delete_papers_domain(domainid):
    con = get_db()
    with con:
        con.execute('delete from papers_domains \
            where domainid = ?', [domainid])
    return id


def delete_papers_authors(authorid):
    con = get_db()
    with con:
        con.execute('delete from papers_authors \
            where authorid = ?', [authorid])
    return id

def delete_papers_tags(keywordid):
    con = get_db()
    with con:
        con.execute('delete from papers_keywords\
            where keywordid = ?', [keywordid])
    return id
