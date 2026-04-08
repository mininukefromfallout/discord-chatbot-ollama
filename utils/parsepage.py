import re
import aiohttp
from urllib.parse import urlparse, unquote

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False

try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


URL_REGEX = re.compile(r'https?://[^\s<>"\']+', re.IGNORECASE)


def extract_urls(text: str) -> list[str]:
    return URL_REGEX.findall(text)


def get_domain(url: str) -> str:
    try:
        host = urlparse(url).netloc.lower()
        return host.removeprefix("www.")
    except Exception:
        return ""


def is_domain_allowed(url: str, allowed_url_domains: list[str]) -> bool:
    domain = get_domain(url)
    if not domain:
        return False
    for allowed in allowed_url_domains:
        clean = allowed.lower().removeprefix("www.")
        if domain == clean or domain.endswith("." + clean):
            return True
    return False


def _is_fandom_url(url: str) -> bool:
    domain = get_domain(url)
    return domain == "fandom.com" or domain.endswith(".fandom.com")


def _extract_text_bs4(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript", "header", "footer", "nav", "aside"]):
        tag.decompose()
    text = soup.get_text(separator=" ")
    return re.sub(r'\s+', ' ', text).strip()


def _extract_text_fallback(html: str) -> str:
    clean = re.sub(r'<[^>]+>', ' ', html)
    return re.sub(r'\s+', ' ', clean).strip()


async def _fetch_fandom(url: str, max_chars: int) -> str | None:
    try:
        parsed = urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        path = parsed.path

        if "/wiki/" in path:
            page_title = unquote(path.split("/wiki/", 1)[1])
        else:
            return None

        api_url = f"{base}/api.php"
        params = {
            "action": "query",
            "titles": page_title,
            "prop": "extracts",
            "explaintext": "true",
            "format": "json",
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json(content_type=None)
                pages = data.get("query", {}).get("pages", {})
                for page in pages.values():
                    extract = page.get("extract", "")
                    if extract:
                        extract = re.sub(r'\s+', ' ', extract).strip()
                        return extract[:max_chars]
                return None
    except Exception as e:
        return None


async def _fetch_with_playwright(url: str, max_chars: int) -> str | None:
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(url, timeout=15000, wait_until="networkidle")
            html = await page.content()
            await browser.close()
            if BS4_AVAILABLE:
                text = _extract_text_bs4(html)
            else:
                text = _extract_text_fallback(html)
            return text[:max_chars] if text else None
    except Exception as e:
        print(f"[parsepage] playwright error ({url}): {e}")
        return None


async def fetch_page_text(url: str, max_chars: int = 3000) -> str | None:
    if _is_fandom_url(url):
        return await _fetch_fandom(url, max_chars)

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xhtml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    print(f"[parsepage] aiohttp {resp.status} for {url}")
                    return None
                content_type = resp.headers.get("Content-Type", "")
                if "text" not in content_type and "json" not in content_type:
                    return None
                raw = await resp.text(errors="ignore")
                if BS4_AVAILABLE and "html" in content_type:
                    text = _extract_text_bs4(raw)
                else:
                    text = _extract_text_fallback(raw)
                if text:
                    return text[:max_chars]
    except Exception as e:
        print(f"[parsepage] aiohttp error ({url}): {e}")

    if PLAYWRIGHT_AVAILABLE:
        print(f"[parsepage] falling back to Playwright for {url}")
        return await _fetch_with_playwright(url, max_chars)

    return None


async def build_url_context(
    message_text: str,
    allowed_url_domains: list[str],
    max_chars: int = 3000
) -> str | None:
    urls = extract_urls(message_text)
    allowed = [u for u in urls if is_domain_allowed(u, allowed_url_domains)]
    if not allowed:
        return None

    blocks = []
    for url in allowed:
        content = await fetch_page_text(url, max_chars=max_chars)
        if content:
            blocks.append(f"[URL: {url}]\n{content}")

    if not blocks:
        return None

    return (
        "The user's message contains URL(s) from approved domains. "
        "The content has been fetched and is provided below for your reference. "
        "Use it to inform your response where relevant:\n\n"
        + "\n\n---\n\n".join(blocks)
    )