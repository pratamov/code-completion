import argparse
import re

from typing import Optional
from lsprotocol import types
from pygls.server import LanguageServer

NUMBER = re.compile(r"\d+")


server = LanguageServer(name="inlay-hint-server", version="v0.1")

def parse_int(chars: str) -> Optional[int]:
    try:
        return int(chars)
    except Exception:
        return None

@server.feature(types.TEXT_DOCUMENT_INLAY_HINT)
def inlay_hints(params: types.InlayHintParams):
    items = []
    document_uri = params.text_document.uri
    document = server.workspace.get_text_document(document_uri)

    start_line = params.range.start.line
    end_line = params.range.end.line

    lines = document.lines[start_line : end_line + 1]
    for lineno, line in enumerate(lines):
        match = COMMENT.match(line)
        if match is not None:
            nb = server.workspace.get_notebook_document(cell_uri=document_uri)
            if nb is not None:
                idx = 0
                for idx, cell in enumerate(nb.cells):
                    if cell.document == document_uri:
                        break

                items.append(
                    types.InlayHint(
                        label=f"notebook: {nb.uri}, cell {idx+1}",
                        kind=types.InlayHintKind.Type,
                        padding_left=False,
                        padding_right=True,
                        position=types.Position(line=lineno, character=match.end()),
                    )
                )

        for match in NUMBER.finditer(line):
            if not match:
                continue

            number = parse_int(match.group(0))
            if number is None:
                continue

            binary_num = bin(number).split("b")[1]
            items.append(
                types.InlayHint(
                    label=f":{binary_num}",
                    kind=types.InlayHintKind.Type,
                    padding_left=False,
                    padding_right=True,
                    position=types.Position(line=lineno, character=match.end()),
                )
            )

    return items


@server.feature(types.INLAY_HINT_RESOLVE)
def inlay_hint_resolve(hint: types.InlayHint):
    try:
        n = int(hint.label[1:], 2)
        hint.tooltip = f"Binary representation of the number: {n}"
    except Exception:
        pass

    return hint


def add_arguments(parser):
    parser.description = "VTScada Code Completion"

    parser.add_argument("--tcp", action="store_true", help="Use TCP server")
    parser.add_argument("--ws", action="store_true", help="Use WebSocket server")
    parser.add_argument("--host", default="127.0.0.1", help="Bind to this address")
    parser.add_argument("--port", type=int, default=2087, help="Bind to this port")

def main():
    parser = argparse.ArgumentParser()
    add_arguments(parser)
    args = parser.parse_args()

    if args.tcp:
        server.start_tcp(args.host, args.port)
    elif args.ws:
        server.start_ws(args.host, args.port)
    else:
        server.start_io()


if __name__ == "__main__":
    main()