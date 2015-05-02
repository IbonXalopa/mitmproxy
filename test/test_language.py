import os
import cStringIO
from libpathod import language
from libpathod.language import base, http, websockets, writer, exceptions
import tutils

language.TESTING = True


def parse_request(s):
    return language.parse_requests(s)[0]


class TestWS:
    def test_expr(self):
        v = base.WS("foo")
        assert v.expr()
        assert v.values(language.Settings())


class TestValueNakedLiteral:
    def test_expr(self):
        v = base.ValueNakedLiteral("foo")
        assert v.expr()

    def test_spec(self):
        v = base.ValueNakedLiteral("foo")
        assert v.spec() == repr(v) == "foo"

        v = base.ValueNakedLiteral("f\x00oo")
        assert v.spec() == repr(v) == r"f\x00oo"


class TestValueLiteral:
    def test_espr(self):
        v = base.ValueLiteral("foo")
        assert v.expr()
        assert v.val == "foo"

        v = base.ValueLiteral("foo\n")
        assert v.expr()
        assert v.val == "foo\n"
        assert repr(v)

    def test_spec(self):
        v = base.ValueLiteral("foo")
        assert v.spec() == r"'foo'"

        v = base.ValueLiteral("f\x00oo")
        assert v.spec() == repr(v) == r"'f\x00oo'"

        v = base.ValueLiteral("\"")
        assert v.spec() == repr(v) == '\'"\''

    def roundtrip(self, spec):
        e = base.ValueLiteral.expr()
        v = base.ValueLiteral(spec)
        v2 = e.parseString(v.spec())
        assert v.val == v2[0].val
        assert v.spec() == v2[0].spec()

    def test_roundtrip(self):
        self.roundtrip("'")
        self.roundtrip('\'')
        self.roundtrip("a")
        self.roundtrip("\"")
        self.roundtrip(r"\\")
        self.roundtrip("200:b'foo':i23,'\\''")


class TestValueGenerate:
    def test_basic(self):
        v = base.Value.parseString("@10b")[0]
        assert v.usize == 10
        assert v.unit == "b"
        assert v.bytes() == 10
        v = base.Value.parseString("@10")[0]
        assert v.unit == "b"
        v = base.Value.parseString("@10k")[0]
        assert v.bytes() == 10240
        v = base.Value.parseString("@10g")[0]
        assert v.bytes() == 1024**3 * 10

        v = base.Value.parseString("@10g,digits")[0]
        assert v.datatype == "digits"
        g = v.get_generator({})
        assert g[:100]

        v = base.Value.parseString("@10,digits")[0]
        assert v.unit == "b"
        assert v.datatype == "digits"

    def test_spec(self):
        v = base.ValueGenerate(1, "b", "bytes")
        assert v.spec() == repr(v) == "@1"

        v = base.ValueGenerate(1, "k", "bytes")
        assert v.spec() == repr(v) == "@1k"

        v = base.ValueGenerate(1, "k", "ascii")
        assert v.spec() == repr(v) == "@1k,ascii"

        v = base.ValueGenerate(1, "b", "ascii")
        assert v.spec() == repr(v) == "@1,ascii"

    def test_freeze(self):
        v = base.ValueGenerate(100, "b", "ascii")
        f = v.freeze(language.Settings())
        assert len(f.val) == 100


class TestValueFile:
    def test_file_value(self):
        v = base.Value.parseString("<'one two'")[0]
        assert str(v)
        assert v.path == "one two"

        v = base.Value.parseString("<path")[0]
        assert v.path == "path"

    def test_access_control(self):
        v = base.Value.parseString("<path")[0]
        with tutils.tmpdir() as t:
            p = os.path.join(t, "path")
            with open(p, "wb") as f:
                f.write("x" * 10000)

            assert v.get_generator(language.Settings(staticdir=t))

            v = base.Value.parseString("<path2")[0]
            tutils.raises(
                exceptions.FileAccessDenied,
                v.get_generator,
                language.Settings(staticdir=t)
            )
            tutils.raises(
                "access disabled",
                v.get_generator,
                language.Settings()
            )

            v = base.Value.parseString("</outside")[0]
            tutils.raises(
                "outside",
                v.get_generator,
                language.Settings(staticdir=t)
            )

    def test_spec(self):
        v = base.Value.parseString("<'one two'")[0]
        v2 = base.Value.parseString(v.spec())[0]
        assert v2.path == "one two"

    def test_freeze(self):
        v = base.Value.parseString("<'one two'")[0]
        v2 = v.freeze({})
        assert v2.path == v.path


class TestMisc:
    def test_generators(self):
        v = base.Value.parseString("'val'")[0]
        g = v.get_generator({})
        assert g[:] == "val"

    def test_value(self):
        assert base.Value.parseString("'val'")[0].val == "val"
        assert base.Value.parseString('"val"')[0].val == "val"
        assert base.Value.parseString('"\'val\'"')[0].val == "'val'"

    def test_path(self):
        e = base.Path.expr()
        assert e.parseString('"/foo"')[0].value.val == "/foo"

        v = base.Path("/foo")
        assert v.value.val == "/foo"

        v = e.parseString("@100")[0]
        v2 = v.freeze({})
        v3 = v2.freeze({})
        assert v2.value.val == v3.value.val
        assert len(v2.value.val) == 100

        s = v.spec()
        assert s == v.expr().parseString(s)[0].spec()

    def test_method(self):
        e = base.Method.expr()
        assert e.parseString("get")[0].value.val == "GET"
        assert e.parseString("'foo'")[0].value.val == "foo"
        assert e.parseString("'get'")[0].value.val == "get"

        assert e.parseString("get")[0].spec() == "get"
        assert e.parseString("'foo'")[0].spec() == "'foo'"

        s = e.parseString("get")[0].spec()
        assert s == e.parseString(s)[0].spec()

        s = e.parseString("'foo'")[0].spec()
        assert s == e.parseString(s)[0].spec()

        v = e.parseString("@100")[0]
        v2 = v.freeze({})
        v3 = v2.freeze({})
        assert v2.value.val == v3.value.val

    def test_raw(self):
        e = base.Raw.expr().parseString("r")[0]
        assert e
        assert e.spec() == "r"
        assert e.freeze({}).spec() == "r"

    def test_body(self):
        e = base.Body.expr()
        v = e.parseString("b'foo'")[0]
        assert v.value.val == "foo"

        v = e.parseString("b@100")[0]
        assert str(v.value) == "@100"
        v2 = v.freeze({})
        v3 = v2.freeze({})
        assert v2.value.val == v3.value.val

        v = e.parseString("b@100g,digits", parseAll=True)[0]
        assert v.value.datatype == "digits"
        assert str(v.value) == "@100g,digits"

        s = v.spec()
        assert s == e.parseString(s)[0].spec()

    def test_pathodspec(self):
        e = base.PathodSpec.expr()
        v = e.parseString("s'200'")[0]
        assert v.value.val == "200"
        tutils.raises(
            language.ParseException,
            e.parseString,
            "s'foo'"
        )

        v = e.parseString('s"200:b@1"')[0]
        assert "@1" in v.spec()
        f = v.freeze({})
        assert "@1" not in f.spec()

    def test_pathodspec_freeze(self):
        e = base.PathodSpec(
            base.ValueLiteral(
                "200:b'foo':i10,'\\''".encode(
                    "string_escape"
                )
            )
        )
        assert e.freeze({})
        assert e.values({})

    def test_code(self):
        e = base.Code.expr()
        v = e.parseString("200")[0]
        assert v.string() == "200"
        assert v.spec() == "200"

        assert v.freeze({}).code == v.code

    def test_reason(self):
        e = base.Reason.expr()
        v = e.parseString("m'msg'")[0]
        assert v.value.val == "msg"

        s = v.spec()
        assert s == e.parseString(s)[0].spec()

        v = e.parseString("m@100")[0]
        v2 = v.freeze({})
        v3 = v2.freeze({})
        assert v2.value.val == v3.value.val

    def test_internal_response(self):
        d = cStringIO.StringIO()
        s = http.make_error_response("foo")
        language.serve(s, d, {})


class TestHeaders:
    def test_header(self):
        e = base.Header.expr()
        v = e.parseString("h'foo'='bar'")[0]
        assert v.key.val == "foo"
        assert v.value.val == "bar"

        v2 = e.parseString(v.spec())[0]
        assert v2.key.val == v.key.val
        assert v2.value.val == v.value.val

        s = v.spec()
        assert s == e.parseString(s)[0].spec()

    def test_header_freeze(self):
        e = base.Header.expr()
        v = e.parseString("h@10=@10'")[0]
        v2 = v.freeze({})
        v3 = v2.freeze({})
        assert v2.key.val == v3.key.val
        assert v2.value.val == v3.value.val

    def test_ctype_shortcut(self):
        e = base.ShortcutContentType.expr()
        v = e.parseString("c'foo'")[0]
        assert v.key.val == "Content-Type"
        assert v.value.val == "foo"

        s = v.spec()
        assert s == e.parseString(s)[0].spec()

        e = base.ShortcutContentType.expr()
        v = e.parseString("c@100")[0]
        v2 = v.freeze({})
        v3 = v2.freeze({})
        assert v2.value.val == v3.value.val

    def test_location_shortcut(self):
        e = base.ShortcutLocation.expr()
        v = e.parseString("l'foo'")[0]
        assert v.key.val == "Location"
        assert v.value.val == "foo"

        s = v.spec()
        assert s == e.parseString(s)[0].spec()

        e = base.ShortcutLocation.expr()
        v = e.parseString("l@100")[0]
        v2 = v.freeze({})
        v3 = v2.freeze({})
        assert v2.value.val == v3.value.val

    def test_shortcuts(self):
        assert language.parse_response("400:c'foo'").headers[0].key.val == "Content-Type"
        assert language.parse_response("400:l'foo'").headers[0].key.val == "Location"

        assert 'Android' in parse_request("get:/:ua").headers[0].value.val
        assert parse_request("get:/:ua").headers[0].key.val == "User-Agent"


class TestShortcutUserAgent:
    def test_location_shortcut(self):
        e = base.ShortcutUserAgent.expr()
        v = e.parseString("ua")[0]
        assert "Android" in str(v.value)
        assert v.spec() == "ua"
        assert v.key.val == "User-Agent"

        v = e.parseString("u'foo'")[0]
        assert "foo" in str(v.value)
        assert "foo" in v.spec()

        v = e.parseString("u@100'")[0]
        assert len(str(v.freeze({}).value)) > 100
        v2 = v.freeze({})
        v3 = v2.freeze({})
        assert v2.value.val == v3.value.val


class Test_Action:
    def test_cmp(self):
        a = base.DisconnectAt(0)
        b = base.DisconnectAt(1)
        c = base.DisconnectAt(0)
        assert a < b
        assert a == c
        l = [b, a]
        l.sort()
        assert l[0].offset == 0

    def test_resolve(self):
        r = parse_request('GET:"/foo"')
        e = base.DisconnectAt("r")
        ret = e.resolve({}, r)
        assert isinstance(ret.offset, int)

    def test_repr(self):
        e = base.DisconnectAt("r")
        assert repr(e)

    def test_freeze(self):
        l = base.DisconnectAt(5)
        assert l.freeze({}).spec() == l.spec()


class TestDisconnects:
    def test_parse_response(self):
        a = language.parse_response("400:d0").actions[0]
        assert a.spec() == "d0"
        a = language.parse_response("400:dr").actions[0]
        assert a.spec() == "dr"

    def test_at(self):
        e = base.DisconnectAt.expr()
        v = e.parseString("d0")[0]
        assert isinstance(v, base.DisconnectAt)
        assert v.offset == 0

        v = e.parseString("d100")[0]
        assert v.offset == 100

        e = base.DisconnectAt.expr()
        v = e.parseString("dr")[0]
        assert v.offset == "r"

    def test_spec(self):
        assert base.DisconnectAt("r").spec() == "dr"
        assert base.DisconnectAt(10).spec() == "d10"


class TestInject:
    def test_parse_response(self):
        a = language.parse_response("400:ir,@100").actions[0]
        assert a.offset == "r"
        assert a.value.datatype == "bytes"
        assert a.value.usize == 100

        a = language.parse_response("400:ia,@100").actions[0]
        assert a.offset == "a"

    def test_at(self):
        e = base.InjectAt.expr()
        v = e.parseString("i0,'foo'")[0]
        assert v.value.val == "foo"
        assert v.offset == 0
        assert isinstance(v, base.InjectAt)

        v = e.parseString("ir,'foo'")[0]
        assert v.offset == "r"

    def test_serve(self):
        s = cStringIO.StringIO()
        r = language.parse_response("400:i0,'foo'")
        assert language.serve(r, s, {})

    def test_spec(self):
        e = base.InjectAt.expr()
        v = e.parseString("i0,'foo'")[0]
        assert v.spec() == 'i0,"foo"'

    def test_spec(self):
        e = base.InjectAt.expr()
        v = e.parseString("i0,@100")[0]
        v2 = v.freeze({})
        v3 = v2.freeze({})
        assert v2.value.val == v3.value.val


class TestPauses:
    def test_parse_response(self):
        e = base.PauseAt.expr()
        v = e.parseString("p10,10")[0]
        assert v.seconds == 10
        assert v.offset == 10

        v = e.parseString("p10,f")[0]
        assert v.seconds == "f"

        v = e.parseString("pr,f")[0]
        assert v.offset == "r"

        v = e.parseString("pa,f")[0]
        assert v.offset == "a"

    def test_request(self):
        r = language.parse_response('400:p10,10')
        assert r.actions[0].spec() == "p10,10"

    def test_spec(self):
        assert base.PauseAt("r", 5).spec() == "pr,5"
        assert base.PauseAt(0, 5).spec() == "p0,5"
        assert base.PauseAt(0, "f").spec() == "p0,f"

    def test_freeze(self):
        l = base.PauseAt("r", 5)
        assert l.freeze({}).spec() == l.spec()


class TestRequest:
    def test_nonascii(self):
        tutils.raises("ascii", parse_request, "get:\xf0")

    def test_err(self):
        tutils.raises(language.ParseException, parse_request, 'GET')

    def test_simple(self):
        r = parse_request('GET:"/foo"')
        assert r.method.string() == "GET"
        assert r.path.string() == "/foo"
        r = parse_request('GET:/foo')
        assert r.path.string() == "/foo"
        r = parse_request('GET:@1k')
        assert len(r.path.string()) == 1024

    def test_multiple(self):
        r = language.parse_requests("GET:/ PUT:/")
        assert r[0].method.string() == "GET"
        assert r[1].method.string() == "PUT"
        assert len(r) == 2

        l = """
            GET
            "/foo"
            ir,@1

            PUT

            "/foo



            bar"

            ir,@1
        """
        r = language.parse_requests(l)
        assert len(r) == 2
        assert r[0].method.string() == "GET"
        assert r[1].method.string() == "PUT"

        l = """
            get:"http://localhost:9999/p/200":ir,@1
            get:"http://localhost:9999/p/200":ir,@2
        """
        r = language.parse_requests(l)
        assert len(r) == 2
        assert r[0].method.string() == "GET"
        assert r[1].method.string() == "GET"

    def test_pathodspec(self):
        l = "get:/p:s'200'"
        r = language.parse_requests(l)
        assert len(r) == 1
        assert len(r[0].tokens) == 3
        assert isinstance(r[0].tokens[2], base.PathodSpec)
        assert r[0].values({})

    def test_render(self):
        s = cStringIO.StringIO()
        r = parse_request("GET:'/foo'")
        assert language.serve(
            r,
            s,
            language.Settings(request_host = "foo.com")
        )

    def test_multiline(self):
        l = """
            GET
            "/foo"
            ir,@1
        """
        r = parse_request(l)
        assert r.method.string() == "GET"
        assert r.path.string() == "/foo"
        assert r.actions

        l = """
            GET

            "/foo



            bar"

            ir,@1
        """
        r = parse_request(l)
        assert r.method.string() == "GET"
        assert r.path.string().endswith("bar")
        assert r.actions

    def test_spec(self):
        def rt(s):
            s = parse_request(s).spec()
            assert parse_request(s).spec() == s
        rt("get:/foo")
        rt("get:/foo:da")

    def test_freeze(self):
        r = parse_request("GET:/:b@100").freeze(language.Settings())
        assert len(r.spec()) > 100

    def test_path_generator(self):
        r = parse_request("GET:@100").freeze(language.Settings())
        assert len(r.spec()) > 100

    def test_websocket(self):
        r = parse_request('ws:/path/')
        res = r.resolve(language.Settings())
        assert res.method.string().lower() == "get"
        assert res.tok(base.Path).value.val == "/path/"
        assert res.tok(base.Method).value.val.lower() == "get"
        assert http.get_header("Upgrade", res.headers).value.val == "websocket"

        r = parse_request('ws:put:/path/')
        res = r.resolve(language.Settings())
        assert r.method.string().lower() == "put"
        assert res.tok(base.Path).value.val == "/path/"
        assert res.tok(base.Method).value.val.lower() == "put"
        assert http.get_header("Upgrade", res.headers).value.val == "websocket"


class TestWebsocketFrame:
    def test_spec(self):
        e = websockets.WebsocketFrame.expr()
        wf = e.parseString("wf:b'foo'")
        assert wf

        assert parse_request("wf:b'foo'")

    def test_values(self):
        r = parse_request("wf:b'foo'")
        assert r.values(language.Settings())


class TestWriteValues:

    def test_send_chunk(self):
        v = "foobarfoobar"
        for bs in range(1, len(v) + 2):
            s = cStringIO.StringIO()
            writer.send_chunk(s, v, bs, 0, len(v))
            assert s.getvalue() == v
            for start in range(len(v)):
                for end in range(len(v)):
                    s = cStringIO.StringIO()
                    writer.send_chunk(s, v, bs, start, end)
                    assert s.getvalue() == v[start:end]

    def test_write_values_inject(self):
        tst = "foo"

        s = cStringIO.StringIO()
        writer.write_values(s, [tst], [(0, "inject", "aaa")], blocksize=5)
        assert s.getvalue() == "aaafoo"

        s = cStringIO.StringIO()
        writer.write_values(s, [tst], [(1, "inject", "aaa")], blocksize=5)
        assert s.getvalue() == "faaaoo"

        s = cStringIO.StringIO()
        writer.write_values(s, [tst], [(1, "inject", "aaa")], blocksize=5)
        assert s.getvalue() == "faaaoo"

    def test_write_values_disconnects(self):
        s = cStringIO.StringIO()
        tst = "foo" * 100
        writer.write_values(s, [tst], [(0, "disconnect")], blocksize=5)
        assert not s.getvalue()

    def test_write_values(self):
        tst = "foobarvoing"
        s = cStringIO.StringIO()
        writer.write_values(s, [tst], [])
        assert s.getvalue() == tst

        for bs in range(1, len(tst) + 2):
            for off in range(len(tst)):
                s = cStringIO.StringIO()
                writer.write_values(
                    s, [tst], [(off, "disconnect")], blocksize=bs
                )
                assert s.getvalue() == tst[:off]

    def test_write_values_pauses(self):
        tst = "".join(str(i) for i in range(10))
        for i in range(2, 10):
            s = cStringIO.StringIO()
            writer.write_values(
                s, [tst], [(2, "pause", 0), (1, "pause", 0)], blocksize=i
            )
            assert s.getvalue() == tst

        for i in range(2, 10):
            s = cStringIO.StringIO()
            writer.write_values(s, [tst], [(1, "pause", 0)], blocksize=i)
            assert s.getvalue() == tst

        tst = ["".join(str(i) for i in range(10))] * 5
        for i in range(2, 10):
            s = cStringIO.StringIO()
            writer.write_values(s, tst[:], [(1, "pause", 0)], blocksize=i)
            assert s.getvalue() == "".join(tst)

    def test_write_values_after(self):
        s = cStringIO.StringIO()
        r = language.parse_response("400:da")
        language.serve(r, s, {})

        s = cStringIO.StringIO()
        r = language.parse_response("400:pa,0")
        language.serve(r, s, {})

        s = cStringIO.StringIO()
        r = language.parse_response("400:ia,'xx'")
        language.serve(r, s, {})
        assert s.getvalue().endswith('xx')


class TestResponse:
    def dummy_response(self):
        return language.parse_response("400'msg'")

    def test_response(self):
        r = language.parse_response("400:m'msg'")
        assert r.code.string() == "400"
        assert r.reason.string() == "msg"

        r = language.parse_response("400:m'msg':b@100b")
        assert r.reason.string() == "msg"
        assert r.body.values({})
        assert str(r)

        r = language.parse_response("200")
        assert r.code.string() == "200"
        assert not r.reason
        assert "OK" in [i[:] for i in r.preamble({})]

    def test_render(self):
        s = cStringIO.StringIO()
        r = language.parse_response("400:m'msg'")
        assert language.serve(r, s, {})

        r = language.parse_response("400:p0,100:dr")
        assert "p0" in r.spec()
        s = r.preview_safe()
        assert "p0" not in s.spec()

    def test_raw(self):
        s = cStringIO.StringIO()
        r = language.parse_response("400:b'foo'")
        language.serve(r, s, {})
        v = s.getvalue()
        assert "Content-Length" in v

        s = cStringIO.StringIO()
        r = language.parse_response("400:b'foo':r")
        language.serve(r, s, {})
        v = s.getvalue()
        assert "Content-Length" not in v

    def test_length(self):
        def testlen(x):
            s = cStringIO.StringIO()
            language.serve(x, s, language.Settings())
            assert x.length(language.Settings()) == len(s.getvalue())
        testlen(language.parse_response("400:m'msg':r"))
        testlen(language.parse_response("400:m'msg':h'foo'='bar':r"))
        testlen(language.parse_response("400:m'msg':h'foo'='bar':b@100b:r"))

    def test_maximum_length(self):
        def testlen(x):
            s = cStringIO.StringIO()
            m = x.maximum_length({})
            language.serve(x, s, {})
            assert m >= len(s.getvalue())

        r = language.parse_response("400:m'msg':b@100:d0")
        testlen(r)

        r = language.parse_response("400:m'msg':b@100:d0:i0,'foo'")
        testlen(r)

        r = language.parse_response("400:m'msg':b@100:d0:i0,'foo'")
        testlen(r)

    def test_parse_err(self):
        tutils.raises(
            language.ParseException, language.parse_response, "400:msg,b:"
        )
        try:
            language.parse_response("400'msg':b:")
        except language.ParseException, v:
            assert v.marked()
            assert str(v)

    def test_nonascii(self):
        tutils.raises("ascii", language.parse_response, "foo:b\xf0")

    def test_parse_header(self):
        r = language.parse_response('400:h"foo"="bar"')
        assert http.get_header("foo", r.headers)

    def test_parse_pause_before(self):
        r = language.parse_response("400:p0,10")
        assert r.actions[0].spec() == "p0,10"

    def test_parse_pause_after(self):
        r = language.parse_response("400:pa,10")
        assert r.actions[0].spec() == "pa,10"

    def test_parse_pause_random(self):
        r = language.parse_response("400:pr,10")
        assert r.actions[0].spec() == "pr,10"

    def test_parse_stress(self):
        # While larger values are known to work on linux, len() technically
        # returns an int and a python 2.7 int on windows has 32bit precision.
        # Therefore, we should keep the body length < 2147483647 bytes in our
        # tests.
        r = language.parse_response("400:b@1g")
        assert r.length({})

    def test_spec(self):
        def rt(s):
            s = language.parse_response(s).spec()
            assert language.parse_response(s).spec() == s
        rt("400:b@100g")
        rt("400")
        rt("400:da")

    def test_websockets(self):
        r = language.parse_response("ws")
        tutils.raises("no websocket key", r.resolve, language.Settings())
        res = r.resolve(language.Settings(websocket_key="foo"))
        assert res.code.string() == "101"
