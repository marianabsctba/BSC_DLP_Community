#!/usr/bin/env python3
import json
import re
import sys
import hashlib
from pathlib import Path

from patterns import PATTERNS


CARD_PATTERN = r"\b(?:\d[ -]*?){13,19}\b"


def digits(value):
    return re.sub(r"\D", "", value)


def validate_cpf(value):
    n = digits(value)

    if len(n) != 11 or len(set(n)) == 1:
        return False

    for size in (9, 10):
        total = sum(
            int(n[i]) * (size + 1 - i)
            for i in range(size)
        )
        d = (total * 10) % 11
        if d == 10:
            d = 0
        if d != int(n[size]):
            return False

    return True


def validate_cnpj(value):
    n = digits(value)

    if len(n) != 14 or len(set(n)) == 1:
        return False

    def calc(base, weights):
        total = sum(int(x) * w for x, w in zip(base, weights))
        r = total % 11
        return 0 if r < 2 else 11 - r

    d1 = calc(n[:12], [5,4,3,2,9,8,7,6,5,4,3,2])
    d2 = calc(n[:12] + str(d1), [6,5,4,3,2,9,8,7,6,5,4,3,2])

    return n[-2:] == f"{d1}{d2}"


def validate_luhn(value):
    n = digits(value)

    if not 13 <= len(n) <= 19:
        return False

    total = 0
    reverse = n[::-1]

    for i, char in enumerate(reverse):
        x = int(char)

        if i % 2 == 1:
            x *= 2
            if x > 9:
                x -= 9

        total += x

    return total % 10 == 0


def mask_value(value):
    clean = str(value)
    if len(clean) <= 4:
        return "*" * len(clean)
    return "*" * (len(clean) - 4) + clean[-4:]

def fingerprint(value):
    return hashlib.sha256(
        str(value).encode("utf-8")
    ).hexdigest()

def classify(text):
    findings = []

    for kind, pattern in PATTERNS.items():
        for match in re.finditer(pattern, text, re.I):

            value = match.group()

            valid = True

            if kind == "CPF":
                valid = validate_cpf(value)

            elif kind == "CNPJ":
                valid = validate_cnpj(value)

            if not valid:
                continue

            findings.append({
                "type": kind,
                "masked_value": mask_value(value),
                "fingerprint": fingerprint(value),
                "offset": match.start(),
                "confidence": "HIGH"
            })

    for match in re.finditer(CARD_PATTERN, text):
        value = match.group().strip()

        if validate_luhn(value):
            findings.append({
                "type": "PAYMENT_CARD",
                "masked_value": mask_value(value),
                "fingerprint": fingerprint(value),
                "offset": match.start(),
                "confidence": "HIGH"
            })

    return findings


def main():
    if len(sys.argv) < 2:
        raise SystemExit(
            "Uso: classifier.py <texto|arquivo>"
        )

    arg = sys.argv[1]
    p = Path(arg)

    if p.exists() and p.is_file():
        text = p.read_text(
            errors="ignore"
        )
        source = str(p)
    else:
        text = arg
        source = "stdin_argument"

    findings = classify(text)

    result = {
        "source": source,
        "findings": findings,
        "finding_count": len(findings),
        "sensitive": bool(findings)
    }

    print(json.dumps(
        result,
        indent=2,
        ensure_ascii=False
    ))


if __name__ == "__main__":
    main()
