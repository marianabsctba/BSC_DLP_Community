package main

import (
	"encoding/binary"
	"testing"
)

func TestDIBToBMP(t *testing.T) {
	dib := make([]byte, 44)
	binary.LittleEndian.PutUint32(dib[0:4], 40)
	binary.LittleEndian.PutUint32(dib[4:8], 1)
	binary.LittleEndian.PutUint32(dib[8:12], 1)
	binary.LittleEndian.PutUint16(dib[12:14], 1)
	binary.LittleEndian.PutUint16(dib[14:16], 24)
	binary.LittleEndian.PutUint32(dib[16:20], biRGB)
	binary.LittleEndian.PutUint32(dib[20:24], 4)
	copy(dib[40:], []byte{0, 0, 0, 0})

	bmp, err := dibToBMP(dib)
	if err != nil {
		t.Fatal(err)
	}
	if len(bmp) != 58 {
		t.Fatalf("BMP length=%d want 58", len(bmp))
	}
	if string(bmp[:2]) != "BM" {
		t.Fatalf("BMP magic=%q", string(bmp[:2]))
	}
	if got := binary.LittleEndian.Uint32(bmp[10:14]); got != 54 {
		t.Fatalf("pixel offset=%d want 54", got)
	}
}

func TestDIBToBMPRejectsBadHeader(t *testing.T) {
	if _, err := dibToBMP([]byte{1, 2, 3}); err == nil {
		t.Fatal("expected short DIB to fail")
	}
}
