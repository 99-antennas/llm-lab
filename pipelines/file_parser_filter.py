"""
File Parser Filter Pipeline for Open WebUI

Intercepts messages containing image attachments, routes them through
llm-lab's /files/upload endpoint for OCR via Claude vision, and prepends
the extracted text to the user's message before it reaches the model.

How it works (Option B):
- Original image block is kept in the message (vision models still see it)
- Extracted text is prepended as a text block so all models get the content
"""
from __future__ import annotations

import base64
from typing import Optional

import httpx
from pydantic import BaseModel


class Pipeline:
    type = "filter"

    class Valves(BaseModel):
        # ["*"] applies this filter to every model in Open WebUI
        pipelines: list[str] = ["*"]
        priority: int = 0
        # URL of the llm-lab API — uses Docker internal networking
        llm_lab_url: str = "http://api:8000"
        enabled: bool = True

    def __init__(self):
        self.name = "File Parser Filter"
        self.valves = self.Valves()

    async def on_startup(self):
        print(f"[file_parser_filter] started — API: {self.valves.llm_lab_url}")

    async def on_shutdown(self):
        pass

    async def inlet(self, body: dict, user: Optional[dict] = None) -> dict:
        if not self.valves.enabled:
            return body

        messages = body.get("messages", [])
        if not messages:
            return body

        # Only process the last user message
        last = messages[-1]
        if last.get("role") != "user":
            return body

        content = last.get("content")
        print(f"[file_parser_filter] content type: {type(content)}")
        if isinstance(content, list):
            for i, block in enumerate(content):
                btype = block.get("type")
                if btype == "image_url":
                    url = block.get("image_url", {}).get("url", "")
                    print(f"[file_parser_filter] block[{i}] image_url prefix: {url[:80]}")
                else:
                    print(f"[file_parser_filter] block[{i}] type: {btype}")
        else:
            print(f"[file_parser_filter] content (str): {str(content)[:120]}")

        if not isinstance(content, list):
            # Plain string content — no file attachments
            return body

        parsed_texts: list[str] = []
        for block in content:
            if block.get("type") != "image_url":
                continue
            url = block.get("image_url", {}).get("url", "")
            if not url.startswith("data:"):
                continue

            # Parse: data:<media_type>;base64,<data>
            try:
                header, b64 = url.split(",", 1)
                media_type = header.split(":")[1].split(";")[0]
            except (ValueError, IndexError):
                continue

            ext = _media_type_to_ext(media_type)
            image_bytes = base64.b64decode(b64)
            text = await _parse_via_api(
                self.valves.llm_lab_url, image_bytes, f"upload{ext}", media_type
            )
            if text:
                parsed_texts.append(f"[Extracted from image]\n{text}")

        if not parsed_texts:
            return body

        prefix = "\n\n".join(parsed_texts)

        # Prepend extracted text to the existing text block, or insert a new one.
        # The original image block is kept so vision-capable models still see it.
        new_content: list[dict] = []
        prepended = False
        for block in content:
            if block.get("type") == "text" and not prepended:
                new_content.append({
                    "type": "text",
                    "text": f"{prefix}\n\n{block['text']}",
                })
                prepended = True
            else:
                new_content.append(block)

        if not prepended:
            new_content.insert(0, {"type": "text", "text": prefix})

        last["content"] = new_content
        return body


def _media_type_to_ext(media_type: str) -> str:
    return {
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/gif": ".gif",
        "image/webp": ".webp",
        "image/heic": ".heic",
        "image/heif": ".heif",
    }.get(media_type, ".jpg")


async def _parse_via_api(
    base_url: str, data: bytes, filename: str, content_type: str
) -> str:
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{base_url}/files/upload",
                files={"file": (filename, data, content_type)},
            )
            resp.raise_for_status()
            return resp.json().get("text", "")
    except Exception as exc:
        print(f"[file_parser_filter] API call failed: {exc}")
        return ""
