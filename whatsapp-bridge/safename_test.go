package main

import (
	"path/filepath"
	"strings"
	"testing"
)

func TestSafeNameStaysInDir(t *testing.T) {
	for _, in := range []string{"../whatsapp.db", "../../oauth/cache.db", "/etc/passwd", "a/b.pdf",
		`..\..\x.db`, "..", ".", "", "/"} {
		out := safeName(in)
		if out == "" || out == "." || out == ".." || strings.ContainsAny(out, `/\`) {
			t.Errorf("safeName(%q) = %q", in, out)
		}
		if got := filepath.Join("/store/chat", out); filepath.Dir(got) != "/store/chat" {
			t.Errorf("safeName(%q) escapes: %q", in, got)
		}
	}
	if got := safeName("report.pdf"); got != "report.pdf" {
		t.Errorf("plain name changed: %q", got)
	}
}

func TestExtractDirectPathKeepsSignature(t *testing.T) {
	url := "https://mmg.whatsapp.net/v/t62.7119-24/123_456_n.enc?ccb=11-4&oh=01_abc&oe=6800AAAA&_nc_sid=5e03e0&mms3=true"
	want := "/v/t62.7119-24/123_456_n.enc?ccb=11-4&oh=01_abc&oe=6800AAAA&_nc_sid=5e03e0"
	if got := extractDirectPathFromURL(url); got != want {
		t.Errorf("got %q, want %q", got, want)
	}
}
