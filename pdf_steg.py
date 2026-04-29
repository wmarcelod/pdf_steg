"""
PDF Steganography via selective text→image rasterization.

Idea: rasterize every page to an image so the visible content is uncopyable,
but reinsert a chosen subset of the original characters as an *invisible*
text layer (PDF render_mode=3) at their exact original positions. Copy/paste
on the resulting PDF returns only the hidden message.

Modes:
    analyze  - print character frequency counts in the input PDF
    hide     - produce a stego PDF carrying a hidden message
    reveal   - extract the hidden text from a stego PDF (just runs text extraction)

Usage:
    python pdf_steg.py analyze input.pdf
    python pdf_steg.py hide input.pdf -m "minha mensagem" -o output.pdf
    python pdf_steg.py reveal output.pdf
"""

from __future__ import annotations

import argparse
import base64
import random
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

import fitz  # PyMuPDF


# ---------- embed/extract: invisible-text steganography ----------

SENTINEL_OPEN = "[STG:"
SENTINEL_CLOSE = ":STG]"
PAYLOAD_RE = re.compile(re.escape(SENTINEL_OPEN) + r"([A-Za-z0-9+/=]+)" + re.escape(SENTINEL_CLOSE))


def encode_payload(message: str) -> str:
    enc = base64.b64encode(message.encode("utf-8")).decode("ascii")
    return f"{SENTINEL_OPEN}{enc}{SENTINEL_CLOSE}"


def decode_payload(text: str) -> str | None:
    m = PAYLOAD_RE.search(text)
    if not m:
        return None
    try:
        return base64.b64decode(m.group(1)).decode("utf-8")
    except Exception:
        return None


# ---------- character extraction ----------

def extract_chars(doc: fitz.Document, include_spaces: bool = False) -> list[dict]:
    """Return every char in the document in reading order, with position metadata.

    Whitespace (spaces, tabs, newlines) is dropped by default since it's
    rarely a reliable steganography carrier — many PDFs render gaps via
    positioning instead of explicit space chars. Pass `include_spaces=True`
    to keep whatever whitespace is actually present in the text stream."""
    chars: list[dict] = []
    for page_idx, page in enumerate(doc):
        raw = page.get_text("rawdict")
        for block in raw.get("blocks", []):
            if block.get("type", 0) != 0:
                continue
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    size = span.get("size", 10.0)
                    for ch in span.get("chars", []):
                        c = ch.get("c", "")
                        if not c:
                            continue
                        if c.isspace() and not include_spaces:
                            continue
                        chars.append({
                            "page": page_idx,
                            "char": c,
                            "origin": ch["origin"],   # (x, y) baseline origin
                            "bbox": ch["bbox"],
                            "size": size,
                        })
    return chars


# ---------- analyze mode ----------

def cmd_analyze(args) -> int:
    doc = fitz.open(args.input)
    chars = extract_chars(doc)
    counter: Counter[str] = Counter(c["char"] for c in chars)

    print(f"Total de caracteres (sem espaços): {sum(counter.values())}")
    print(f"Páginas: {doc.page_count}")
    print()
    print("Frequência por caractere:")
    for ch, n in sorted(counter.items(), key=lambda kv: (-kv[1], kv[0])):
        repr_ch = ch if ch.isprintable() else repr(ch)
        print(f"  {repr_ch!s:>4}  {n}")
    return 0


# ---------- hide mode ----------

def _normalize(c: str) -> str:
    """Casefold + strip diacritics so 'á' matches 'a'."""
    nfkd = unicodedata.normalize("NFKD", c)
    return "".join(ch for ch in nfkd if not unicodedata.combining(ch)).casefold()


MODES = ("greedy", "spread", "even")


def find_positions(
    chars: list[dict],
    message: str,
    rng: random.Random | None = None,
    mode: str = "spread",
    include_spaces: bool = False,
) -> tuple[list[int] | None, str | None]:
    """Pick a position in `chars` for each char of `message`, in increasing
    order. Whitespace chars in `message` are skipped unless `include_spaces`
    is True. Three modes:
        greedy - first matching char after the cursor (clusters near the start)
        spread - uniform random inside the feasible window (default, scattered)
        even   - even slicing of the feasible window with random jitter inside
    Returns (indices, None) or (None, missing_char) if infeasible."""
    if mode not in MODES:
        raise ValueError(f"unknown mode {mode!r}; expected one of {MODES}")
    rng = rng or random.Random()
    msg_chars = list(message) if include_spaces else [c for c in message if not c.isspace()]
    if not msg_chars:
        return [], None

    # Per-message-char list of doc positions whose char matches (case + diacritic insensitive).
    candidates: list[list[int]] = []
    for mc in msg_chars:
        norm = _normalize(mc)
        positions = [i for i, c in enumerate(chars) if _normalize(c["char"]) == norm]
        if not positions:
            return None, mc
        candidates.append(positions)

    # latest[i] = greatest doc position usable for message[i] such that
    # message[i+1:] can still be placed strictly after it. Walk from the end.
    M = len(msg_chars)
    latest = [0] * M
    upper_excl = len(chars)
    for i in range(M - 1, -1, -1):
        feasible = [p for p in candidates[i] if p < upper_excl]
        if not feasible:
            return None, msg_chars[i]
        latest[i] = feasible[-1]
        upper_excl = latest[i]

    # Stratified sampling: divide the document length into M slots so each
    # letter targets a different region. Snap policy: try to land inside the
    # ideal slot (random for spread / center for even); if the slot has no
    # occurrence of this letter, prefer the closest candidate AHEAD of the
    # slot — falling back to behind only if no forward option exists. This
    # preserves room for subsequent letters and maximizes global spread.
    N = len(chars)
    slot_size = N / M

    indices: list[int] = []
    cursor = 0
    for i in range(M):
        pool = [p for p in candidates[i] if cursor <= p <= latest[i]]
        if not pool:
            return None, msg_chars[i]

        if mode == "greedy":
            chosen = pool[0]
        else:
            slot_lo = int(i * slot_size)
            slot_hi = int((i + 1) * slot_size) - 1
            lo = max(cursor, slot_lo)
            hi = min(latest[i], slot_hi)

            if lo > hi:
                # Ideal slot lies entirely outside the feasibility window;
                # operate over the full window.
                lo, hi = cursor, latest[i]

            in_slot = [p for p in pool if lo <= p <= hi]
            if in_slot:
                if mode == "spread":
                    chosen = rng.choice(in_slot)
                else:  # even
                    center = (lo + hi) // 2
                    chosen = min(in_slot, key=lambda p: (abs(p - center), p))
            else:
                # Empty slot: prefer forward, but keep some randomness in
                # spread mode by sampling a target within the next slot's
                # worth of space and snapping to the nearest occurrence.
                forward = [p for p in pool if p > hi]
                if not forward:
                    chosen = pool[-1]  # closest backward as last resort
                elif mode == "spread":
                    t_hi = min(latest[i], hi + int(slot_size * 1.5))
                    target = rng.randint(hi + 1, t_hi) if t_hi > hi else hi + 1
                    chosen = min(forward, key=lambda p: (abs(p - target), p))
                else:  # even — deterministic closest forward
                    chosen = forward[0]

        indices.append(chosen)
        cursor = chosen + 1

    return indices, None


def build_hidden_pdf(
    input_path: Path,
    output_path: Path,
    message: str,
    dpi: int,
    seed: int | None = None,
    mode: str = "spread",
    strict: bool = False,
) -> int:
    src = fitz.open(input_path)
    chars = extract_chars(src, include_spaces=True)
    rng = random.Random(seed) if seed is not None else random.Random()

    # Default behavior: try to embed every char of the message, including
    # whitespace and punctuation. If a char can't be placed (no occurrence in
    # the PDF, or no feasible ordering) and it's NOT alphanumeric, drop it
    # with a warning and continue. Alphanumerics still hard-fail because
    # losing a letter would silently corrupt the message. `strict=True`
    # disables the auto-drop and hard-fails on any missing char.
    msg = message
    dropped: dict[str, int] = {}
    while True:
        indices, missing = find_positions(
            chars, msg, rng=rng, mode=mode, include_spaces=True,
        )
        if indices is not None:
            break
        if missing.isalnum() or strict:
            label = "essencial" if missing.isalnum() else "obrigatório (--strict)"
            print(
                f"Erro: caractere {label} {missing!r} não pode ser inserido "
                f"(ausente no PDF ou ordem inviável).",
                file=sys.stderr,
            )
            return 2
        new_msg = msg.replace(missing, "")
        if new_msg == msg:
            print(f"Erro interno: remoção de {missing!r} não teve efeito.", file=sys.stderr)
            return 2
        dropped[missing] = dropped.get(missing, 0) + (len(msg) - len(new_msg))
        msg = new_msg

    for ch, n in dropped.items():
        shown = repr(ch) if ch.isprintable() and not ch.isspace() else f"U+{ord(ch):04X}"
        print(
            f"aviso: caractere {shown} omitido {n}x (sem ocorrência viável no PDF).",
            file=sys.stderr,
        )

    by_page: dict[int, list[dict]] = {}
    for idx in indices:
        c = chars[idx]
        by_page.setdefault(c["page"], []).append(c)

    out = fitz.open()
    for page_idx, src_page in enumerate(src):
        rect = src_page.rect
        new_page = out.new_page(width=rect.width, height=rect.height)
        pix = src_page.get_pixmap(dpi=dpi, alpha=False)
        new_page.insert_image(rect, pixmap=pix)
        for c in by_page.get(page_idx, []):
            ox, oy = c["origin"]
            new_page.insert_text(
                fitz.Point(ox, oy), c["char"],
                fontsize=c["size"], fontname="helv", render_mode=3,
            )

    out.save(output_path, garbage=4, deflate=True)

    extracted = "".join(p.get_text() for p in fitz.open(output_path)).strip()
    print(f"OK. PDF gerado em: {output_path}")
    if msg != message:
        print(f"Mensagem original: {message!r}")
        print(f"Mensagem efetivamente embutida: {msg!r}")
    else:
        print(f"Mensagem embutida: {msg!r}")
    print(f"Texto extraível do PDF gerado: {extracted!r}")
    return 0


def cmd_hide(args) -> int:
    message = args.message
    if not message:
        print("Digite a mensagem (uma linha, Enter para confirmar):")
        message = input("> ")
    if not message.strip():
        print("Mensagem vazia.", file=sys.stderr)
        return 2

    out_path = Path(args.output) if args.output else Path(args.input).with_name(
        Path(args.input).stem + "_stego.pdf"
    )
    return build_hidden_pdf(
        Path(args.input), out_path, message,
        dpi=args.dpi, seed=args.seed, mode=args.mode, strict=args.strict,
    )


# ---------- reveal mode ----------

# ---------- embed mode (preserves visible text by default) ----------

def cmd_embed(args) -> int:
    src_path = Path(args.input)
    out_path = Path(args.output) if args.output else src_path.with_name(
        src_path.stem + "_embed.pdf"
    )

    if not args.message or not args.message.strip():
        print("Mensagem vazia.", file=sys.stderr)
        return 2

    payload = encode_payload(args.message)
    src = fitz.open(src_path)

    if args.rasterize:
        out = fitz.open()
        for page_idx, src_page in enumerate(src):
            rect = src_page.rect
            new_page = out.new_page(width=rect.width, height=rect.height)
            pix = src_page.get_pixmap(dpi=args.dpi, alpha=False)
            new_page.insert_image(rect, pixmap=pix)
            if page_idx == 0:
                new_page.insert_text(
                    fitz.Point(2, rect.height - 2),
                    payload, fontsize=1, render_mode=3,
                )
        out.save(out_path, garbage=4, deflate=True)
    else:
        page = src[0]
        page.insert_text(
            fitz.Point(2, page.rect.height - 2),
            payload, fontsize=1, render_mode=3,
        )
        src.save(out_path, garbage=4, deflate=True)

    extracted_back = decode_payload("".join(p.get_text() for p in fitz.open(out_path)))
    print(f"OK. PDF gerado em: {out_path}")
    print(f"Modo: {'rasterizado (texto vira imagem)' if args.rasterize else 'preserva texto visível'}")
    print(f"Mensagem embutida: {args.message!r}")
    print(f"Round-trip: {extracted_back!r}")
    return 0


def cmd_extract(args) -> int:
    doc = fitz.open(args.input)
    text = "".join(page.get_text() for page in doc)
    msg = decode_payload(text)
    if msg is None:
        print("Nenhuma mensagem encontrada.", file=sys.stderr)
        return 1
    print(msg)
    return 0


def cmd_reveal(args) -> int:
    doc = fitz.open(args.input)
    raw = "".join(page.get_text() for page in doc)
    compact = "".join(raw.split())  # remove all whitespace
    print("--- texto extraído (bruto) ---")
    print(raw.strip() or "(vazio)")
    print("--- compacto (sem espaços/quebras) ---")
    print(compact or "(vazio)")
    return 0


# ---------- entrypoint ----------

def main() -> int:
    parser = argparse.ArgumentParser(description="PDF steganography via selective rasterization.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_an = sub.add_parser("analyze", help="conta letras do PDF")
    p_an.add_argument("input")
    p_an.set_defaults(func=cmd_analyze)

    p_hi = sub.add_parser("hide", help="gera PDF com mensagem escondida")
    p_hi.add_argument("input")
    p_hi.add_argument("-m", "--message", help="mensagem secreta (se omitido, pergunta no terminal)")
    p_hi.add_argument("-o", "--output", help="caminho do PDF de saída")
    p_hi.add_argument("--dpi", type=int, default=220, help="resolução da rasterização (default: 220)")
    p_hi.add_argument("--seed", type=int, default=None,
                      help="seed para tornar a escolha aleatória reprodutível")
    p_hi.add_argument("--mode", choices=MODES, default="spread",
                      help="estratégia de escolha de posições: "
                           "greedy=primeira ocorrência (concentra no começo); "
                           "spread=aleatório uniforme na faixa viável (default); "
                           "even=fatias iguais do documento com jitter")
    p_hi.add_argument("--strict", action="store_true",
                      help="hard-fail se qualquer caractere da mensagem (inclusive "
                           "espaços e símbolos) não puder ser inserido. Sem essa flag "
                           "o default é descartar com aviso quem não couber.")
    p_hi.set_defaults(func=cmd_hide)

    p_re = sub.add_parser("reveal", help="extrai texto (mensagem escondida) do PDF")
    p_re.add_argument("input")
    p_re.set_defaults(func=cmd_reveal)

    p_em = sub.add_parser("embed",
                          help="embute mensagem invisível preservando texto visível (default) ou rasterizando")
    p_em.add_argument("input")
    p_em.add_argument("-m", "--message", required=True, help="mensagem secreta")
    p_em.add_argument("-o", "--output", help="caminho do PDF de saída")
    p_em.add_argument("--rasterize", action="store_true",
                      help="rasteriza o texto visível em imagem (Ctrl+A devolve só a mensagem)")
    p_em.add_argument("--dpi", type=int, default=220,
                      help="resolução da rasterização quando --rasterize estiver ativo")
    p_em.set_defaults(func=cmd_embed)

    p_ex = sub.add_parser("extract", help="extrai a mensagem embutida por 'embed'")
    p_ex.add_argument("input")
    p_ex.set_defaults(func=cmd_extract)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
