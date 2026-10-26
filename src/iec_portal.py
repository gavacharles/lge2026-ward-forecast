"""Minimal client for the IEC results download portal (ASP.NET WebForms).

The portal at results.elections.org.za/home/Downloads/{ME,NPE}-Results is driven by
postbacks: choose election -> choose report -> choose criteria -> download.
"""
import re

import requests
from bs4 import BeautifulSoup

BASE = "https://results.elections.org.za/home/Downloads/"
UA = {"User-Agent": "Mozilla/5.0 (research; election-prediction-model)"}


class Portal:
    def __init__(self, page="ME-Results"):
        self.url = BASE + page
        self.s = requests.Session()
        self.s.headers.update(UA)
        self.soup = self._parse(self.s.get(self.url, timeout=60))

    @staticmethod
    def _parse(resp):
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "html.parser")

    def form_state(self):
        """All current form values (hidden fields, selects, checked inputs)."""
        data = {}
        for inp in self.soup.select("form input[name]"):
            t = (inp.get("type") or "text").lower()
            if t in ("submit", "button", "image"):
                continue
            if t in ("checkbox", "radio") and not inp.has_attr("checked"):
                continue
            data[inp["name"]] = inp.get("value", "")
        for sel in self.soup.select("form select[name]"):
            opt = sel.find("option", selected=True) or sel.find("option")
            data[sel["name"]] = opt.get("value", "") if opt else ""
        return data

    def selects(self):
        return {
            sel["name"]: [(o.get("value"), o.get_text(strip=True)) for o in sel.find_all("option")]
            for sel in self.soup.select("form select[name]")
        }

    def buttons(self):
        out = []
        for b in self.soup.select("form input[type=submit], form input[type=image], form a[href*=__doPostBack]"):
            out.append((b.name, b.get("name") or b.get("href"), b.get("value") or b.get_text(strip=True)))
        return out

    def postback(self, target, overrides=None, argument=""):
        data = self.form_state()
        data.update(overrides or {})
        data["__EVENTTARGET"] = target
        data["__EVENTARGUMENT"] = argument
        r = self.s.post(self.url, data=data, timeout=120)
        self.soup = self._parse(r)
        return self

    def submit(self, button_name, overrides=None):
        """Click a submit button; returns the raw response (may be a file)."""
        data = self.form_state()
        data.update(overrides or {})
        data["__EVENTTARGET"] = ""
        data[button_name] = self.soup.find(attrs={"name": button_name}).get("value", "")
        r = self.s.post(self.url, data=data, timeout=600)
        r.raise_for_status()
        ctype = r.headers.get("Content-Type", "")
        if "html" in ctype:
            self.soup = BeautifulSoup(r.text, "html.parser")
        return r

    def text(self, n=3000):
        t = self.soup.get_text(" ", strip=True)
        return re.sub(r"\s+", " ", t)[:n]
