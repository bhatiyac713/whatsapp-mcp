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
