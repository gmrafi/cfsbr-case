#!/usr/bin/env python3
"""
tools/crossref_deposit.py

CFSBR / C.A.S.E. - Crossref XML DOI registration helper.

Pipeline:
  1) Pull metadata JSON from PubPub (URL from env until KU/PubPub team confirms
     the per-pub export suffix).
  2) Build Crossref journal-issue XML (deposit schema 4.4.0, namespace
     http://www.crossref.org/schema/4.4.0).
  3) Multipart-POST (operation=doMDUpload, login_id, login_passwd, fname=<XML>)
     to https://test.crossref.org/servlet/deposit (default) or
     https://doi.crossref.org/servlet/deposit (with --live).
  4) Best-effort status poll (endpoint left as a TODO placeholder - the exact
     Crossref polling URL was not confirmed via a single authoritative source
     in this session; only the deposit endpoint and form fields were verified).

Credentials are read from environment variables only (# never hardcode secrets).

Verified Crossref parameters used in this script (sources cited in README
section of this file - fetched this session):

  Source 1: https://www.crossref.org/documentation/register-maintain-records/direct-deposit-xml/https-post/
    - Production POST endpoint: https://doi.crossref.org/servlet/deposit
    - Test POST endpoint:       https://test.crossref.org/servlet/deposit
    - Required multipart form fields:
        operation=doMDUpload (default), login_id, login_passwd, fname
    - Limits: 10 MB per upload; 10,000 pending submissions per user (HTTP 429
      otherwise)
    - EncType: multipart/form-data (HTTPS POST)

  Source 2: https://www.crossref.org/documentation/schema-library/markup-guide-record-types/journals-and-articles/
    - Root element:  <doi_batch xmlns="http://www.crossref.org/schema/4.4.0" version="4.4.0" ...>
    - <body><journal> children in order: <journal_metadata>, <journal_issue>, <journal_article>
    - Article DOI block: <doi_data><doi>10.xxxx/yyyy</doi><resource>URL</resource></doi_data>

Parameter not fully verified this session (TODO):
  - Submission status polling endpoint (community forum hints
    /servlet/submissionDownload, but no single authoritative URL confirmed).
    poll_status() below is intentionally a log-only stub.
"""
from __future__ import annotations
import argparse
import json
import os
import sys
import time
import uuid
import urllib.request
import urllib.error
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom import minidom

NS = "http://www.crossref.org/schema/4.4.0"
SCHEMA_VERSION = "4.4.0"

PROD_ENDPOINT = "https://doi.crossref.org/servlet/deposit"
TEST_ENDPOINT = "https://test.crossref.org/servlet/deposit"


# ---------- PubPub metadata fetch (URL from env until KU team confirms suffix) ----------
def fetch_pubpub_metadata(url):
    if not url:
        return {}
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


# ---------- XML builder (Crossref 4.4.0 journal_article) ----------
def build_doi_batch_xml(meta, volume, issue, year):
    batch = Element(
        "{%s}doi_batch" % NS,
        attrib={
            "version": SCHEMA_VERSION,
            "xsi:schemaLocation": "%s http://www.crossref.org/schemas/crossref4.4.0.xsd",
        },
    )
    batch.set("xmlns:xsi", "http://www.w3.org/2001/XMLSchema-instance")

    head = SubElement(batch, "head")
    SubElement(head, "doi_batch_id").text = "case.cfsbr.v%d.i%d.%s" % (
        volume, issue, uuid.uuid4().hex[:6])
    SubElement(head, "timestamp").text = str(int(time.time()))
    SubElement(head, "depositor_name").text = meta.get("depositor_name", "CFSBR / C.A.S.E.")
    SubElement(head, "depositor_email").text = meta.get("depositor_email", "deposit@case.cfsbr.com")
    SubElement(head, "registrant").text = meta.get("registrant", "Centre for Fintech and Strategic Business Research")

    body = SubElement(batch, "body")
    journal = SubElement(body, "journal")
    journal.set("language", "en")

    jmeta = SubElement(journal, "journal_metadata")
    SubElement(jmeta, "full_title").text = meta.get(
        "journal_title", "C.A.S.E. - Class Assignment Series: Edition")
    SubElement(jmeta, "abbrev_title").text = meta.get("journal_abbrev", "CFSBR C.A.S.E.")
    SubElement(jmeta, "issn").text = meta.get("issn", "")  # fill when registered
    SubElement(jmeta, "publisher").text = meta.get(
        "publisher", "Centre for Fintech and Strategic Business Research")

    # Journal issue (volume/issue/year)
    jissue = SubElement(journal, "journal_issue")
    pd_print = SubElement(jissue, "publication_date", attrib={"media_type": "print"})
    SubElement(pd_print, "year").text = str(year)
    SubElement(pd_print, "month").text = str(meta.get("month", 7)).zfill(2)
    SubElement(jissue, "journal_volume").text = "Volume %d" % volume
    SubElement(jissue, "issue").text = "Issue %d" % issue

    # Journal article
    article = SubElement(journal, "journal_article", attrib={"publication_type": "full_text"})

    titles = SubElement(article, "titles")
    SubElement(titles, "title").text = meta["title"]

    contribs = SubElement(article, "contributors")
    for idx, person in enumerate(meta.get("authors", [])):
        c = SubElement(
            contribs, "person_name",
            attrib={
                "contributor_role": "author",
                "sequence": "first" if idx == 0 else "additional",
            },
        )
        SubElement(c, "given_name").text = person.get("given", "")
        SubElement(c, "surname").text = person.get("surname", "")
        if person.get("orcid"):
            SubElement(c, "ORCID").text = "https://orcid.org/%s" % person["orcid"]

    if meta.get("abstract"):
        SubElement(article, "abstract").text = meta["abstract"]

    pdate = SubElement(article, "publication_date", attrib={"media_type": "online"})
    SubElement(pdate, "year").text = str(year)
    SubElement(pdate, "month").text = str(meta.get("month", 7)).zfill(2)
    SubElement(pdate, "day").text = str(meta.get("day", 1)).zfill(2)

    if meta.get("pages"):
        pages = SubElement(article, "pages")
        for side in ("first_page", "last_page"):
            if side in meta["pages"]:
                SubElement(pages, side).text = str(meta["pages"][side])

    pitem = SubElement(article, "publisher_item")
    SubElement(pitem, "item_number").text = meta.get(
        "item_number", "v%d.i%d.p1" % (volume, issue))

    doi_data = SubElement(article, "doi_data")
    SubElement(doi_data, "doi").text = meta["doi"]
    SubElement(doi_data, "resource").text = meta["resource_url"]

    return _prettify(batch)


def _prettify(el):
    rough = tostring(el, encoding="utf-8")
    return minidom.parseString(rough).toprettyxml(indent="  ", encoding="utf-8")


# ---------- multipart upload (operation, login_id, login_passwd, fname) ----------
def post_deposit(xml_bytes, live):
    endpoint = PROD_ENDPOINT if live else TEST_ENDPOINT
    boundary = "------CFSBRCASE" + uuid.uuid4().hex
    parts = []
    for name, value in [
        ("operation", "doMDUpload"),
        ("login_id", _env("CROSSREF_LOGIN_ID")),
        ("login_passwd", _env("CROSSREF_LOGIN_PASSWD")),
    ]:
        parts += [
            ("--%s\r\n" % boundary).encode("utf-8"),
            ('Content-Disposition: form-data; name="%s"\r\n\r\n' % name).encode("utf-8"),
            value.encode("utf-8"),
            b"\r\n",
        ]
    parts += [
        ("--%s\r\n" % boundary).encode("utf-8"),
        b'Content-Disposition: form-data; name="fname"; filename="crossref_deposit.xml"\r\n',
        b"Content-Type: application/xml; charset=utf-8\r\n\r\n",
        xml_bytes,
        b"\r\n",
        ("--%s--\r\n" % boundary).encode("utf-8"),
    ]
    body = b"".join(parts)
    req = urllib.request.Request(
        endpoint, data=body, method="POST",
        headers={"Content-Type": "multipart/form-data; boundary=%s" % boundary},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, r.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")


# ---------- status poll (TODO: exact polling endpoint not single-source confirmed) ----------
def poll_status(tracking_id, live):
    if not tracking_id:
        return
    print("[crossref-deposit] tracking id: %s" % tracking_id)
    print(
        "[crossref-deposit] status polling endpoint not configured - "
        "see README TODO; poll_status is a log-only stub."
    )


def _env(name):
    v = os.environ.get(name)
    if not v:
        sys.stderr.write("ERROR: environment variable %s not set\n" % name)
        sys.exit(2)
    return v


# ---------- MAIN ----------
def main():
    ap = argparse.ArgumentParser(
        description="Crossref XML DOI registration helper (CFSBR / C.A.S.E.)"
    )
    ap.add_argument("--pub", required=True, help="Path to PubPub-derived metadata JSON")
    ap.add_argument("--volume", type=int, required=True)
    ap.add_argument("--issue", type=int, required=True)
    ap.add_argument("--year", type=int, required=True)
    ap.add_argument(
        "--dry-run", action="store_true",
        help="Build XML only; do not POST (default if credentials missing).",
    )
    ap.add_argument(
        "--live", action="store_true",
        help="Use production endpoint (https://doi.crossref.org/...). Requires --no-dry-run AND credentials.",
    )
    ap.add_argument("--out", default="out/crossref_deposit.xml", help="XML output path")
    args = ap.parse_args()

    with open(args.pub, "r", encoding="utf-8") as f:
        meta_in = json.load(f)
    meta = {
        "depositor_name": "CFSBR",
        "depositor_email": "deposit@case.cfsbr.com",
        "registrant": "Centre for Fintech and Strategic Business Research",
        "journal_title": meta_in.get(
            "journal_title", "C.A.S.E. - Class Assignment Series: Edition"),
        "journal_abbrev": "CFSBR C.A.S.E.",
        "issn": meta_in.get("issn", ""),
        "publisher": "Centre for Fintech and Strategic Business Research",
        "title": meta_in["title"],
        "authors": meta_in.get("authors", []),
        "abstract": meta_in.get("abstract", ""),
        "doi": meta_in["doi"],
        "resource_url": meta_in["resource_url"],
        "pages": meta_in.get("pages", {}),
        "item_number": meta_in.get("item_number", "v%d.i%d.p1" % (args.volume, args.issue)),
        "month": meta_in.get("month", 7),
        "day": meta_in.get("day", 1),
    }

    xml_bytes = build_doi_batch_xml(meta, args.volume, args.issue, args.year)
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "wb") as f:
        f.write(xml_bytes)

    print("[crossref-deposit] operation          = doMDUpload")
    print(
        "[crossref-deposit] endpoint (%s)    = %s"
        % ("live" if args.live else "test", PROD_ENDPOINT if args.live else TEST_ENDPOINT)
    )
    print("[crossref-deposit] schema             = %s" % SCHEMA_VERSION)
    print("[crossref-deposit] XML payload bytes  = %d" % len(xml_bytes))
    print("[crossref-deposit] DOI prefix         = %s" % os.environ.get("CROSSREF_DOI_PREFIX", "10.67226"))
    print(
        "[crossref-deposit] journal_article    = title=%r, DOI=%s"
        % (meta["title"], meta["doi"])
    )
    print("[crossref-deposit] XML written to     = %s" % args.out)

    if args.dry_run or not (
        os.environ.get("CROSSREF_LOGIN_ID") and os.environ.get("CROSSREF_LOGIN_PASSWD")
    ):
        print("[crossref-deposit] DRY-RUN: skip POST")
        return 0

    status, body = post_deposit(xml_bytes, live=args.live)
    print("[crossref-deposit] POST status        = %d" % status)
    print("[crossref-deposit] --- response (first 400 chars) ---")
    print(body[:400])

    tracking_id = None
    for line in body.splitlines():
        if "submission_dirlist" in line or "batch_id" in line:
            tracking_id = line.strip()
            break
    poll_status(tracking_id, live=args.live)
    return 0


if __name__ == "__main__":
    sys.exit(main())
