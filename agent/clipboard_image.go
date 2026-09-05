package main

import (
	"encoding/binary"
	"fmt"
)

const (
	biRGB            = 0
	biBitFields      = 3
	biAlphaBitFields = 6
)

func dibToBMP(dib []byte) ([]byte, error) {
	if len(dib) < 12 {
		return nil, fmt.Errorf("DIB header is too small")
	}

	headerSize := int(binary.LittleEndian.Uint32(dib[0:4]))
	if headerSize < 12 || headerSize > len(dib) {
		return nil, fmt.Errorf("invalid DIB header size: %d", headerSize)
	}

	paletteEntries := 0
	paletteEntrySize := 4
	extraMasks := 0

	switch {
	case headerSize == 12:
		bitCount := int(binary.LittleEndian.Uint16(dib[10:12]))
		if bitCount > 0 && bitCount <= 8 {
			paletteEntries = 1 << bitCount
			paletteEntrySize = 3
		}

	case headerSize >= 40:
		if len(dib) < 40 {
			return nil, fmt.Errorf("truncated BITMAPINFOHEADER")
		}

		bitCount := int(binary.LittleEndian.Uint16(dib[14:16]))
		compression := binary.LittleEndian.Uint32(dib[16:20])
		clrUsed := int(binary.LittleEndian.Uint32(dib[32:36]))

		if clrUsed > 0 {
			paletteEntries = clrUsed
		} else if bitCount > 0 && bitCount <= 8 {
			paletteEntries = 1 << bitCount
		}

		if headerSize == 40 {
			switch compression {
			case biBitFields:
				extraMasks = 12
			case biAlphaBitFields:
				extraMasks = 16
			}
		}

	default:
		return nil, fmt.Errorf("unsupported DIB header size: %d", headerSize)
	}

	pixelOffset := 14 + headerSize + extraMasks + paletteEntries*paletteEntrySize
	fileSize := 14 + len(dib)

	if pixelOffset > fileSize {
		return nil, fmt.Errorf("invalid DIB pixel offset: %d > %d", pixelOffset, fileSize)
	}

	bmp := make([]byte, fileSize)
	bmp[0] = 'B'
	bmp[1] = 'M'
	binary.LittleEndian.PutUint32(bmp[2:6], uint32(fileSize))
	binary.LittleEndian.PutUint32(bmp[10:14], uint32(pixelOffset))
	copy(bmp[14:], dib)

	return bmp, nil
}
