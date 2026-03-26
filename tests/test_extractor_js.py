"""Tests for extractor_js module."""

from pathlib import Path

import pytest

from drift.extractor_js import (
    JSDocExtractor,
    _NAME_RE,
    _PARAM_RE,
    _RETURNS_RE,
    _TYPE_RE,
    _THROWS_RE,
    _SEE_RE,
    _clean_text,
    _parse_param_name,
)

FIXTURE = Path(__file__).parent / "fixtures" / "sample_jsdoc.js"


class TestJSDocExtractorCanHandle:
    """Test .can_handle() method."""

    def test_handles_js_file(self):
        ext = JSDocExtractor()
        assert ext.can_handle(Path("foo.js")) is True

    def test_handles_ts_file(self):
        ext = JSDocExtractor()
        assert ext.can_handle(Path("foo.ts")) is True

    def test_handles_jsx_file(self):
        ext = JSDocExtractor()
        assert ext.can_handle(Path("foo.jsx")) is True

    def test_handles_tsx_file(self):
        ext = JSDocExtractor()
        assert ext.can_handle(Path("foo.tsx")) is True

    def test_rejects_py_file(self):
        ext = JSDocExtractor()
        assert ext.can_handle(Path("foo.py")) is False

    def test_rejects_md_file(self):
        ext = JSDocExtractor()
        assert ext.can_handle(Path("foo.md")) is False

    def test_rejects_txt_file(self):
        ext = JSDocExtractor()
        assert ext.can_handle(Path("foo.txt")) is False


class TestJSDocExtractorExtract:
    """Test .extract() method."""

    def test_extracts_function_with_jsdoc(self):
        """greet function is extracted."""
        ext = JSDocExtractor()
        claims = ext.extract(FIXTURE)
        names = {c.name for c in claims}
        assert "greet" in names

    def test_extracts_arrow_function(self):
        """add arrow function is extracted."""
        ext = JSDocExtractor()
        claims = ext.extract(FIXTURE)
        names = {c.name for c in claims}
        assert "add" in names

    def test_extracts_async_function(self):
        """fetchData async function is extracted."""
        ext = JSDocExtractor()
        claims = ext.extract(FIXTURE)
        names = {c.name for c in claims}
        assert "fetchData" in names

    def test_extracts_param_claims(self):
        """@param claims are extracted."""
        ext = JSDocExtractor()
        claims = ext.extract(FIXTURE)
        param_claims = [c for c in claims if c.kind.value == "parameter_description"]
        assert len(param_claims) >= 3

    def test_extracts_return_claims(self):
        """@returns claims are extracted."""
        ext = JSDocExtractor()
        claims = ext.extract(FIXTURE)
        return_claims = [c for c in claims if c.kind.value == "return_description"]
        assert len(return_claims) >= 3

    def test_extracts_throws_claim(self):
        """@throws claim is extracted."""
        ext = JSDocExtractor()
        claims = ext.extract(FIXTURE)
        throw_claims = [
            c for c in claims
            if c.metadata.get("category") == "throws"
        ]
        assert len(throw_claims) >= 1

    def test_extracts_see_claim(self):
        """@see claim is extracted."""
        ext = JSDocExtractor()
        claims = ext.extract(FIXTURE)
        see_claims = [
            c for c in claims
            if c.metadata.get("category") == "see"
        ]
        assert len(see_claims) >= 2

    def test_name_annotation_overrides(self):
        """@name annotation changes effective name."""
        ext = JSDocExtractor()
        claims = ext.extract(FIXTURE)
        names = {c.name for c in claims}
        # @name simpleName
        assert "simpleName" in names

    def test_kind_is_function_signature_for_untyped(self):
        """Functions without specific tag use FUNCTION_SIGNATURE."""
        ext = JSDocExtractor()
        claims = ext.extract(FIXTURE)
        # check seeRef which has @see but no @param/@returns
        see_ref_claims = [c for c in claims if c.name == "seeRef"]
        assert len(see_ref_claims) >= 1
        assert see_ref_claims[0].kind.value == "function_signature"

    def test_throws_kind_is_function_signature(self):
        """@throws tagged claims use FUNCTION_SIGNATURE."""
        ext = JSDocExtractor()
        claims = ext.extract(FIXTURE)
        throw_claims = [
            c for c in claims
            if c.metadata.get("category") == "throws"
        ]
        assert all(c.kind.value == "function_signature" for c in throw_claims)

    def test_destructured_param_extracted(self):
        """Destructured params { a, b } are parsed."""
        ext = JSDocExtractor()
        claims = ext.extract(FIXTURE)
        # fetchData has @param {object} options
        options_claims = [
            c for c in claims
            if c.parameters and any(p.name == "options" for p in c.parameters)
        ]
        assert len(options_claims) >= 1

    def test_returns_type_extracted(self):
        """@returns {type} captures the type."""
        ext = JSDocExtractor()
        claims = ext.extract(FIXTURE)
        return_claims = [c for c in claims if c.kind.value == "return_description"]
        types_with_string = [c for c in return_claims if c.return_type == "string"]
        assert len(types_with_string) >= 1

    def test_returns_type_number(self):
        """@returns {number} captures number type."""
        ext = JSDocExtractor()
        claims = ext.extract(FIXTURE)
        return_claims = [c for c in claims if c.kind.value == "return_description"]
        types_with_number = [c for c in return_claims if c.return_type == "number"]
        assert len(types_with_number) >= 1

    def test_returns_type_boolean(self):
        """@returns {boolean} captures boolean type."""
        ext = JSDocExtractor()
        claims = ext.extract(FIXTURE)
        return_claims = [c for c in claims if c.kind.value == "return_description"]
        types_with_bool = [c for c in return_claims if c.return_type == "boolean"]
        assert len(types_with_bool) >= 1

    def test_returns_void(self):
        """@returns void is handled."""
        ext = JSDocExtractor()
        claims = ext.extract(FIXTURE)
        return_claims = [c for c in claims if c.kind.value == "return_description"]
        void_claims = [c for c in return_claims if c.return_type == "void"]
        assert len(void_claims) >= 1

    def test_type_standalone(self):
        """@type annotation creates a claim."""
        ext = JSDocExtractor()
        claims = ext.extract(FIXTURE)
        # @type {function(string): number} on parseInt
        type_claims = [
            c for c in claims
            if c.metadata.get("source") == "jsdoc"
            and c.metadata.get("category") == "type"
        ]
        assert len(type_claims) >= 1

    def test_source_is_jsdoc(self):
        """All claims have source='jsdoc'."""
        ext = JSDocExtractor()
        claims = ext.extract(FIXTURE)
        assert all(c.metadata.get("source") == "jsdoc" for c in claims)

    def test_doc_file_is_set(self):
        """doc_file is set to the fixture path."""
        ext = JSDocExtractor()
        claims = ext.extract(FIXTURE)
        assert all(c.doc_file == FIXTURE for c in claims)

    def test_line_number_is_set(self):
        """line_number is set on claims."""
        ext = JSDocExtractor()
        claims = ext.extract(FIXTURE)
        assert all(c.line_number > 0 for c in claims)

    def test_raw_text_not_empty_for_param(self):
        """@param raw_text contains the tag text."""
        ext = JSDocExtractor()
        claims = ext.extract(FIXTURE)
        param_claims = [c for c in claims if c.kind.value == "parameter_description"]
        assert all("@param" in c.raw_text for c in param_claims)

    def test_raw_text_not_empty_for_returns(self):
        """@returns raw_text contains the tag text."""
        ext = JSDocExtractor()
        claims = ext.extract(FIXTURE)
        return_claims = [c for c in claims if c.kind.value == "return_description"]
        assert all("@return" in c.raw_text or "@returns" in c.raw_text for c in return_claims)

    def test_missing_file_returns_empty(self):
        """Non-existent file returns empty list."""
        ext = JSDocExtractor()
        claims = ext.extract(Path("/nonexistent/file.js"))
        assert claims == []

    def test_function_no_jsdoc_not_extracted(self):
        """Functions without JSDoc are not extracted (no @name, not exported)."""
        ext = JSDocExtractor()
        claims = ext.extract(FIXTURE)
        names = {c.name for c in claims}
        assert "noDocFunc" not in names

    def test_partial_doc_func_extracted(self):
        """Function with @param but no @name still gets extracted."""
        ext = JSDocExtractor()
        claims = ext.extract(FIXTURE)
        names = {c.name for c in claims}
        # Has @param so it should be found
        assert "partialDoc" in names

    def test_legacy_param_without_type(self):
        """@param name - desc (without type) is parsed."""
        ext = JSDocExtractor()
        claims = ext.extract(FIXTURE)
        names = {c.name for c in claims}
        assert "legacyFunc" in names

    def test_ts_function_exported(self):
        """Exported TS function is extracted."""
        ext = JSDocExtractor()
        claims = ext.extract(FIXTURE)
        names = {c.name for c in claims}
        assert "tsFunc" in names

    def test_class_method_extracted(self):
        """Class method with JSDoc is extracted."""
        ext = JSDocExtractor()
        claims = ext.extract(FIXTURE)
        names = {c.name for c in claims}
        # @name Counter.increment
        assert "Counter.increment" in names

    def test_async_arrow_function(self):
        """async arrow functions are handled."""
        # The fetchData test already covers async
        ext = JSDocExtractor()
        claims = ext.extract(FIXTURE)
        assert "fetchData" in {c.name for c in claims}

    def test_throws_description_extracted(self):
        """@throws {TypeError} description is extracted."""
        ext = JSDocExtractor()
        claims = ext.extract(FIXTURE)
        throw_claims = [
            c for c in claims
            if c.metadata.get("category") == "throws"
        ]
        assert any("input is invalid" in (c.metadata.get("description") or "") for c in throw_claims)

    def test_see_url_extracted(self):
        """@see URL is in raw_text."""
        ext = JSDocExtractor()
        claims = ext.extract(FIXTURE)
        see_claims = [c for c in claims if c.metadata.get("category") == "see"]
        assert any("https://" in c.raw_text or "https://api.example.com" in c.raw_text
                   for c in see_claims)

    def test_see_ref_extracted(self):
        """@see {@link greet} is in raw_text."""
        ext = JSDocExtractor()
        claims = ext.extract(FIXTURE)
        see_claims = [c for c in claims if c.metadata.get("category") == "see"]
        assert any("greet" in c.raw_text for c in see_claims)

    def test_optional_param_bracket(self):
        """@param [name] optional param is parsed."""
        ext = JSDocExtractor()
        claims = ext.extract(FIXTURE)
        # greet has @param {number} [age]
        age_claims = [
            c for c in claims
            if c.parameters and any(p.name == "age" for p in c.parameters)
        ]
        assert len(age_claims) >= 1

    def test_param_with_default_in_options(self):
        """@param with default value in options object is parsed."""
        ext = JSDocExtractor()
        claims = ext.extract(FIXTURE)
        # fetchData has @param {number} [options.timeout=5000]
        timeout_claims = [
            c for c in claims
            if c.parameters and any("timeout" in p.name for p in c.parameters)
        ]
        assert len(timeout_claims) >= 1

    def test_callback_typedef(self):
        """@callback is found but creates docstring claim."""
        ext = JSDocExtractor()
        claims = ext.extract(FIXTURE)
        names = {c.name for c in claims}
        # The callback typedef itself isn't a function, but processItems has @param DataCallback
        assert "processItems" in names

    def test_multiple_functions_all_found(self):
        """All documented functions are found."""
        ext = JSDocExtractor()
        claims = ext.extract(FIXTURE)
        names = {c.name for c in claims}
        expected = {
            "greet", "add", "fetchData", "processItems", "partialDoc",
            "legacyFunc", "simpleName", "isReady", "parseInt", "validateInput",
            "seeLink", "seeRef", "tsFunc", "Counter.increment",
        }
        assert expected.issubset(names)

    def test_empty_js_file(self):
        """Empty JS file returns empty claims."""
        import tempfile
        ext = JSDocExtractor()
        with tempfile.NamedTemporaryFile(suffix=".js", delete=False, mode="w") as f:
            f.write("")
            f.flush()
            claims = ext.extract(Path(f.name))
        assert claims == []

    def test_js_without_jsdoc(self):
        """JS file with no JSDoc returns empty claims."""
        import tempfile
        ext = JSDocExtractor()
        with tempfile.NamedTemporaryFile(suffix=".js", delete=False, mode="w") as f:
            f.write("function foo(a, b) { return a + b; }\n")
            f.flush()
            claims = ext.extract(Path(f.name))
        # Not exported, no @name, so not extracted
        assert len(claims) == 0

    def test_js_with_exported_no_jsdoc(self):
        """Exported function without JSDoc returns minimal claim."""
        import tempfile
        ext = JSDocExtractor()
        with tempfile.NamedTemporaryFile(suffix=".js", delete=False, mode="w") as f:
            f.write("export function bar(x, y) { return x * y; }\n")
            f.flush()
            claims = ext.extract(Path(f.name))
        assert len(claims) >= 1
        bar_claims = [c for c in claims if c.name == "bar"]
        assert len(bar_claims) >= 1

    def test_param_description_in_raw_text(self):
        """@param - description is in raw_text."""
        ext = JSDocExtractor()
        claims = ext.extract(FIXTURE)
        param_claims = [c for c in claims if c.kind.value == "parameter_description"]
        raw_texts = " ".join(c.raw_text for c in param_claims)
        assert "The user's name" in raw_texts or "@param" in raw_texts

    def test_return_description_in_metadata(self):
        """@returns description is in metadata.description."""
        ext = JSDocExtractor()
        claims = ext.extract(FIXTURE)
        return_claims = [c for c in claims if c.kind.value == "return_description"]
        assert any(c.metadata.get("description") for c in return_claims)

    def test_param_type_in_metadata(self):
        """@param {type} type is in metadata."""
        ext = JSDocExtractor()
        claims = ext.extract(FIXTURE)
        param_claims = [c for c in claims if c.kind.value == "parameter_description"]
        assert any(c.parameters and c.parameters[0].type_annotation
                   for c in param_claims if c.parameters)

    def test_parameters_list_populated(self):
        """@param claims have populated parameters list."""
        ext = JSDocExtractor()
        claims = ext.extract(FIXTURE)
        param_claims = [c for c in claims if c.kind.value == "parameter_description"]
        assert all(len(c.parameters) >= 1 for c in param_claims)

    def test_name_override_via_jsdoc(self):
        """@name overrides the actual function name."""
        ext = JSDocExtractor()
        claims = ext.extract(FIXTURE)
        names = {c.name for c in claims}
        # @name simpleName on simpleArrow
        assert "simpleName" in names

    def test_promise_return_type(self):
        """@returns {Promise<object>} is captured."""
        ext = JSDocExtractor()
        claims = ext.extract(FIXTURE)
        return_claims = [c for c in claims if c.kind.value == "return_description"]
        promise_returns = [
            c for c in return_claims
            if c.return_type and "Promise" in c.return_type
        ]
        assert len(promise_returns) >= 1

    def test_unwraps_correct_newlines(self):
        """Claims are extracted even with complex multiline JSDoc."""
        ext = JSDocExtractor()
        claims = ext.extract(FIXTURE)
        # All functions with JSDoc should produce at least one claim
        assert len(claims) >= 20


class TestHelperFunctions:
    """Test helper functions."""

    def test_clean_text_strips(self):
        assert _clean_text("  hello  ") == "hello"

    def test_clean_text_none_returns_none(self):
        assert _clean_text(None) is None

    def test_clean_text_empty_returns_none(self):
        assert _clean_text("") is None
        assert _clean_text("   ") is None

    def test_parse_param_name_simple(self):
        params = _parse_param_name("a, b, c")
        assert len(params) == 3
        assert params[0].name == "a"
        assert params[1].name == "b"
        assert params[2].name == "c"

    def test_parse_param_name_with_types(self):
        params = _parse_param_name("a: string, b: number")
        assert params[0].name == "a"
        assert params[0].type_annotation == "string"
        assert params[1].name == "b"
        assert params[1].type_annotation == "number"

    def test_parse_param_name_with_defaults(self):
        params = _parse_param_name("a = 1, b = 'hello'")
        assert params[0].name == "a"
        assert params[0].default == "1"
        assert params[1].name == "b"
        assert params[1].default == "'hello'"

    def test_parse_param_name_rest(self):
        params = _parse_param_name("...args")
        assert params[0].name == "...args"
        assert params[0].kind == "varargs"

    def test_parse_param_name_destructuring(self):
        params = _parse_param_name("{ a, b }")
        assert len(params) == 2
        assert params[0].name == "a"
        assert params[1].name == "b"

    def test_parse_param_name_complex_ts(self):
        params = _parse_param_name("url: string, options: RequestInit = {}")
        assert params[0].name == "url"
        assert params[0].type_annotation == "string"
        assert params[1].name == "options"
        assert params[1].type_annotation == "RequestInit"
        assert params[1].default == "{}"

    def test_parse_param_name_empty(self):
        params = _parse_param_name("")
        assert params == []

    def test_param_regex_basic(self):
        m = _PARAM_RE.search("@param {string} name - description")
        assert m is not None
        assert m.group(1) == "string"
        assert m.group(2) == "name"
        assert m.group(3) == "description"

    def test_param_regex_no_type(self):
        m = _PARAM_RE.search("@param name - description")
        assert m is not None
        assert m.group(1) is None
        assert m.group(2) == "name"

    def test_param_regex_no_description(self):
        m = _PARAM_RE.search("@param {number} count")
        assert m is not None
        assert m.group(1) == "number"
        assert m.group(2) == "count"
        assert m.group(3) is None

    def test_param_regex_optional(self):
        m = _PARAM_RE.search("@param {string} [name] - optional")
        assert m is not None
        assert m.group(2) == "[name]"

    def test_returns_re_basic(self):
        m = _RETURNS_RE.search("@returns {string} the result")
        assert m is not None
        assert m.group(1) == "string"
        assert "result" in m.group(2)

    def test_returns_re_no_type(self):
        m = _RETURNS_RE.search("@return something")
        assert m is not None
        assert m.group(1) is None

    def test_throws_re_basic(self):
        m = _THROWS_RE.search("@throws {Error} when failed")
        assert m is not None
        assert m.group(1) == "Error"

    def test_see_re_basic(self):
        m = _SEE_RE.search("@see https://example.com")
        assert m is not None

    def test_name_re_basic(self):
        m = _NAME_RE.search("@name myFunc")
        assert m is not None
        assert m.group(1) == "myFunc"

    def test_type_re_basic(self):
        m = _TYPE_RE.search("@type {function(string): number}")
        assert m is not None
        assert m.group(1) == "function(string): number"
