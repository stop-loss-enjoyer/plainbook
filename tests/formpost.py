# -*- coding: utf-8 -*-
"""A form of a page read the way a browser sends it, for the tests that post
a form exactly as it was drawn rather than as a test remembers it.

A hand-written dict sends what its author thought the form holds, and the
forms are where a field left out deletes a record's data (invariants 2 and
14): a test of that has to send what the page draws, no more and no less."""
from html.parser import HTMLParser

_BOOLEAN = ("checked", "selected", "disabled", "multiple")


class _Forms(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.forms = []             # [(attrs, [(name, value), ...])]
        self.form = None
        self.template = 0           # a <template> is inert: nothing in it is sent
        self.select = None          # (name, multiple, [(value, selected, disabled)])
        self.option = None          # [value or None, selected, disabled, text]
        self.textarea = None        # [name, text]

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        for k in _BOOLEAN:
            a[k] = k in a
        if tag == "template":
            self.template += 1
        if self.template:
            return
        if tag == "form":
            self.form = (a, [])
            self.forms.append(self.form)
            return
        if self.form is None:
            return
        name = a.get("name")
        if tag == "input":
            kind = (a.get("type") or "text").lower()
            if not name or a["disabled"] or kind in ("file", "submit", "button",
                                                     "reset", "image"):
                return
            if kind in ("checkbox", "radio"):
                if a["checked"]:
                    self.form[1].append((name, a.get("value") or "on"))
                return
            self.form[1].append((name, a.get("value") or ""))
        elif tag == "textarea" and name and not a["disabled"]:
            self.textarea = [name, ""]
        elif tag == "select":
            self.select = (name if name and not a["disabled"] else None,
                           a["multiple"], [])
        elif tag == "option" and self.select is not None:
            self._end_option()
            self.option = [a.get("value"), a["selected"], a["disabled"], ""]

    def handle_endtag(self, tag):
        if tag == "template":
            self.template = max(0, self.template - 1)
            return
        if self.template or self.form is None:
            return
        if tag == "textarea" and self.textarea:
            text = self.textarea[1]
            # the parser keeps the newline a browser drops after <textarea>
            if text.startswith("\r\n"):
                text = text[2:]
            elif text.startswith("\n"):
                text = text[1:]
            self.form[1].append((self.textarea[0], text))
            self.textarea = None
        elif tag == "option":
            self._end_option()
        elif tag == "select" and self.select is not None:
            self._end_option()
            name, multiple, options = self.select
            self.select = None
            if name is None:
                return
            chosen = [v for v, sel, off in options if sel and not off]
            if not multiple:
                if chosen:
                    chosen = chosen[-1:]
                else:
                    chosen = [v for v, sel, off in options if not off][:1]
            self.form[1].extend((name, v) for v in chosen)
        elif tag == "form":
            self.form = None

    def _end_option(self):
        if self.option is None or self.select is None:
            return
        value, selected, disabled, text = self.option
        self.option = None
        self.select[2].append((" ".join(text.split()) if value is None else value,
                               selected, disabled))

    def handle_data(self, data):
        if self.template:
            return
        if self.textarea is not None:
            self.textarea[1] += data
        elif self.option is not None:
            self.option[3] += data


def form_fields(html, action=None):
    """The fields of the form whose action is `action` (the first form that
    posts, when None), as {name: [values]} in the order of the page: ready for
    `urlencode(..., doseq=True)`."""
    p = _Forms()
    p.feed(html)
    p.close()
    for attrs, pairs in p.forms:
        if action is None and (attrs.get("method") or "get").lower() != "post":
            continue
        if action is not None and attrs.get("action") != action:
            continue
        fields = {}
        for name, value in pairs:
            fields.setdefault(name, []).append(value)
        return fields
    raise LookupError(f"no form posting to {action!r}")
