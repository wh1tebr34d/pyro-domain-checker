from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
import socket
import ssl
import json
import time
import re
import html as html_lib
import os
import shutil


BASE_DIR = Path(__file__).resolve().parent
TARGETS_FILE = BASE_DIR / "Targets.txt"

RESULTS_FILE = BASE_DIR / "results.json"
REAL_FILE = BASE_DIR / "working.txt"
POSSIBLE_FILE = BASE_DIR / "possible.txt"
REJECTED_FILE = BASE_DIR / "rejected.txt"

TIMEOUT = 7
THREADS = 30
READ_BYTES = 160_000

PRINT_REJECTED = False
PROGRESS_WIDTH = 34

os.system("")
USE_COLOR = not bool(os.environ.get("NO_COLOR"))

RESET = "\033[0m"
DIM = "\033[2m"
BOLD = "\033[1m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
CYAN = "\033[36m"
GRAY = "\033[90m"


def c(text: str, code: str) -> str:
    if not USE_COLOR:
        return text
    return f"{code}{text}{RESET}"


def term_width() -> int:
    return max(80, shutil.get_terminal_size((100, 20)).columns)


BANNER = r"""
██████╗ ██╗   ██╗██████╗  ██████╗ 
██╔══██╗╚██╗ ██╔╝██╔══██╗██╔═══██╗
██████╔╝ ╚████╔╝ ██████╔╝██║   ██║
██╔═══╝   ╚██╔╝  ██╔══██╗██║   ██║
██║        ██║   ██║  ██║╚██████╔╝
╚═╝        ╚═╝   ╚═╝  ╚═╝ ╚═════╝ 
"""


TAGLINE = "TLD rotation + parked-page filtering + content scoring"


def clean_screen():
    os.system("cls" if os.name == "nt" else "clear")


def hr(char: str = "─"):
    print(c(char * min(term_width(), 96), GRAY))


def print_banner():
    clean_screen()
    print(c(BANNER, CYAN))
    print(c("PYRO DOMAIN CHECKER", BOLD))
    print(c(TAGLINE, GRAY))
    hr()


def print_kv(label: str, value):
    print(f"  {c(label.ljust(12), GRAY)} {value}")


def clip(value, limit: int) -> str:
    value = str(value) if value is not None else ""
    value = value.replace("\n", " ").replace("\r", " ")
    value = re.sub(r"\s+", " ", value).strip()
    if len(value) <= limit:
        return value
    return value[: max(0, limit - 1)] + "…"


def verdict_label(verdict: str) -> str:
    if verdict == "working":
        return c("working", GREEN)
    if verdict == "Could be working":
        return c("Could be working", YELLOW)
    if verdict in ["PARKED", "PLACEHOLDER", "EMPTY", "LOW_CONFIDENCE"]:
        return c(verdict, GRAY)
    if verdict in ["TIMEOUT", "DNS_FAIL", "CONNECTION_FAIL", "CONNECTION_REFUSED", "TLS_FAIL", "ERROR"]:
        return c(verdict, RED)
    return verdict


def print_result_table(title: str, rows, color_code: str):
    print()
    print(c(title, color_code + BOLD))
    hr()

    if not rows:
        print(c("  none", GRAY))
        return

    print(
        c("  # ", GRAY)
        + c(f"{'DOMAIN':<27} {'SCORE':<5} {'CODE':<5} {'TIME':<7} TITLE", GRAY)
    )

    for idx, r in enumerate(rows, 1):
        domain = clip(r.get("domain", ""), 27)
        title_text = clip(r.get("title") or "(no title)", 58)
        code = r.get("http_code") or "-"
        rt = r.get("response_time")
        rt = f"{rt}s" if rt is not None else "-"
        score = r.get("score", 0)

        print(
            f"  {c(str(idx).rjust(2), GRAY)} "
            f"{domain:<27} "
            f"{str(score):<5} "
            f"{str(code):<5} "
            f"{rt:<7} "
            f"{title_text}"
        )


def print_saved_files():
    print()
    print(c("FILES", BOLD))
    hr()
    print_kv("real", REAL_FILE.name)
    print_kv("possible", POSSIBLE_FILE.name)
    print_kv("rejected", REJECTED_FILE.name)
    print_kv("full json", RESULTS_FILE.name)

pproviders = [
    "godaddy.com",
    "afternic.com",
    "sedo.com",
    "dan.com",
    "hugedomains.com",
    "namecheap.com",
    "parkingcrew.net",
    "bodis.com",
    "above.com",
    "squadhelp.com",
    "sav.com",
    "domainmarket.com",
    "uniregistry.com",
    "dynadot.com",
    "porkbun.com",
    "spaceship.com",
    "name.com",
    "domain.com",
]

pkeywords = [
    "domain name is for sale",
    "this domain is for sale",
    "is for sale",
    "buy this domain",
    "make an offer",
    "get a price in less than 24 hours",
    "premium domain",
    "verified domain",
    "domain parking",
    "parked free",
    "this domain has expired",
    "renew this domain",
    "backorder this domain",
    "resources and information",
    "related searches",
    "may be for sale",
    "inquire about this domain",
    "purchase this domain",
    "godaddy",
    "afternic",
    "sedo",
    "hugedomains",
    "parkingcrew",
    "bodis",
    "namecheap parking",
]

btitles = [
    "redirecting",
    "loading",
    "index of /",
    "my blog",
    "site is undergoing maintenance",
    "under maintenance",
    "coming soon",
    "under construction",
    "resources and information",
    "website coming soon",
    "default web site page",
    "apache2 ubuntu default page",
    "welcome to nginx",
    "domain parked",
    "domain for sale",
    "this domain is for sale",
    "just a moment",
    "attention required",
    "access denied",
    "forbidden",
]

bkeywords = [
    "resources and information",
    "this domain may be for sale",
    "this domain is for sale",
    "domain name is for sale",
    "buy this domain",
    "make an offer",
    "related searches",
    "index of /",
    "apache server at",
    "nginx server",
    "coming soon",
    "under construction",
    "site is undergoing maintenance",
    "website coming soon",
    "default web site page",
    "apache2 ubuntu default page",
    "welcome to nginx",
    "parked domain",
    "domain parking",
    "generated by cloudfront",
    "there is no site configured at this address",
    "the site you were looking for couldn't be found",
    "heroku | no such app",
    "project not found",
    "deployment not found",
    "this page is parked free",
]

BLOCKED_KEYWORDS = [
    "checking your browser",
    "verify you are human",
    "captcha",
    "access denied",
    "attention required",
    "cloudflare ray id",
    "ddos-guard",
]

GOOD_GENERIC_KEYWORDS = [
    "home",
    "search",
    "login",
    "sign in",
    "register",
    "privacy",
    "terms",
    "contact",
    "about",
    "popular",
    "latest",
    "browse",
    "category",
    "watch",
    "stream",
    "episode",
    "movie",
    "series",
    "download",
]


def clean_host(raw: str) -> str:
    raw = raw.strip().lower()
    raw = raw.replace("https://", "")
    raw = raw.replace("http://", "")
    raw = raw.split("/")[0]
    raw = raw.split(":")[0]

    if raw.startswith("www."):
        raw = raw[4:]

    if "." in raw:
        raw = raw.split(".")[0]

    raw = re.sub(r"[^a-z0-9-]", "", raw)
    return raw


def load_tlds():
    if not TARGETS_FILE.exists():
        TARGETS_FILE.write_text(
            "com\nnet\norg\nio\nto\ntv\ngg\ncc\nxyz\nsite\nonline\n",
            encoding="utf-8"
        )
        print("[+] Created Targets.txt with default TLDs.")
        return []

    tlds = []

    for line in TARGETS_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip().lower()

        if not line or line.startswith("#"):
            continue

        line = line.replace(".", "")
        line = re.sub(r"[^a-z0-9-]", "", line)

        if line:
            tlds.append(line)

    return sorted(set(tlds))


def dns_check(domain: str):
    try:
        ip = socket.gethostbyname(domain)
        return True, ip
    except socket.gaierror:
        return False, None


def extract_title(page: str) -> str:
    match = re.search(r"<title[^>]*>(.*?)</title>", page, re.IGNORECASE | re.DOTALL)

    if not match:
        return ""

    title = match.group(1)
    title = html_lib.unescape(title)
    title = re.sub(r"\s+", " ", title)
    return title.strip()


def strip_html(page: str) -> str:
    page = re.sub(r"<script.*?</script>", " ", page, flags=re.IGNORECASE | re.DOTALL)
    page = re.sub(r"<style.*?</style>", " ", page, flags=re.IGNORECASE | re.DOTALL)
    page = re.sub(r"<[^>]+>", " ", page)
    page = html_lib.unescape(page)
    page = re.sub(r"\s+", " ", page)
    return page.strip()


def count_links(page: str) -> int:
    return len(re.findall(r"<a\s+", page, flags=re.IGNORECASE))


def is_domain_only_title(title: str, domain: str, host: str) -> bool:
    title_l = title.lower().strip()
    title_l = title_l.replace("www.", "")

    if not title_l:
        return False

    domain_l = domain.lower()
    host_l = host.lower()

    cleaned = re.sub(r"[^a-z0-9.-]", "", title_l)

    if cleaned == domain_l:
        return True

    if cleaned == host_l:
        return True

    if cleaned in [f"{host_l}.com", f"{host_l}.net", f"{host_l}.org"]:
        return True

    return False


def is_parked_page(domain: str, final_url: str, title: str, page: str):
    combined = f"{final_url}\n{title}\n{page}".lower()

    for provider in pproviders:
        if provider in final_url.lower():
            return True, f"PARKED_PROVIDER:{provider}"

    hits = []

    for keyword in pkeywords:
        if keyword in combined:
            hits.append(keyword)

    if len(hits) >= 1:
        return True, f"PARKED_KEYWORD:{hits[0]}"

    if domain.lower() in combined and "for sale" in combined:
        return True, "PARKED_FOR_SALE"

    return False, None


def classify_page(host: str, domain: str, final_url: str, title: str, page: str):
    text = strip_html(page).lower()
    title_l = title.lower().strip()
    parked, reason = is_parked_page(domain, final_url, title, page)

    if parked:
        return "PARKED", reason, 0

    for keyword in BLOCKED_KEYWORDS:
        if keyword in text or keyword in title_l:
            return "BLOCKED", f"BLOCKED:{keyword}", 0

    if is_domain_only_title(title, domain, host):
        return "PLACEHOLDER", "DOMAIN_ONLY_TITLE", 0

    if not title_l and len(text) < 500:
        return "EMPTY", "EMPTY_OR_TINY_PAGE", 0

    for keyword in btitles:
        if keyword in title_l:
            return "PLACEHOLDER", f"BAD_TITLE:{keyword}", 0

    for keyword in bkeywords:
        if keyword in text:
            return "PLACEHOLDER", f"BAD_BODY:{keyword}", 0

    score = 0
    reasons = []

    if host in title_l:
        score += 2
        reasons.append("HOST_IN_TITLE")

    if host in text:
        score += 2
        reasons.append("HOST_IN_BODY")

    if len(text) >= 1500:
        score += 1
        reasons.append("ENOUGH_TEXT")

    links = count_links(page)

    if links >= 8:
        score += 1
        reasons.append(f"LINKS:{links}")

    good_hits = []

    for keyword in GOOD_GENERIC_KEYWORDS:
        if keyword in text:
            good_hits.append(keyword)

    if len(good_hits) >= 3:
        score += 2
        reasons.append(f"GOOD_WORDS:{','.join(good_hits[:5])}")
    elif len(good_hits) >= 1:
        score += 1
        reasons.append(f"GOOD_WORDS:{','.join(good_hits[:3])}")

    if title_l and len(title_l) >= 4:
        score += 1
        reasons.append("GOOD_TITLE")

    if score >= 5:
        return "REAL", "|".join(reasons), score

    if score >= 3:
        return "POSSIBLE", "|".join(reasons), score

    return "LOW_CONFIDENCE", "|".join(reasons) if reasons else "LOW_SCORE", score


def http_check(host: str, domain: str, url: str):
    req = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) PyroDomainChecker/2.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
    )

    try:
        start = time.time()

        with urlopen(req, timeout=TIMEOUT) as response:
            elapsed = round(time.time() - start, 2)

            code = response.status
            final_url = response.geturl()

            raw = response.read(READ_BYTES)
            page = raw.decode("utf-8", errors="ignore")
            title = extract_title(page)

            if not (200 <= code < 400):
                return {
                    "verdict": "HTTP_ERROR",
                    "working": False,
                    "possible": False,
                    "alive": True,
                    "status": f"HTTP_{code}",
                    "http_code": code,
                    "title": title,
                    "final_url": final_url,
                    "response_time": elapsed,
                    "score": 0,
                    "error": f"HTTP {code}",
                }

            verdict, reason, score = classify_page(host, domain, final_url, title, page)

            return {
                "verdict": verdict,
                "working": verdict == "REAL",
                "possible": verdict == "POSSIBLE",
                "alive": True,
                "status": verdict,
                "http_code": code,
                "title": title,
                "final_url": final_url,
                "response_time": elapsed,
                "score": score,
                "error": reason,
            }

    except HTTPError as e:
        return {
            "verdict": "HTTP_ERROR",
            "working": False,
            "possible": False,
            "alive": True,
            "status": f"HTTP_{e.code}",
            "http_code": e.code,
            "title": "",
            "final_url": url,
            "response_time": None,
            "score": 0,
            "error": f"HTTP error {e.code}",
        }

    except ssl.SSLCertVerificationError:
        return {
            "verdict": "TLS_FAIL",
            "working": False,
            "possible": False,
            "alive": True,
            "status": "TLS_FAIL",
            "http_code": None,
            "title": "",
            "final_url": url,
            "response_time": None,
            "score": 0,
            "error": "TLS certificate verification failed",
        }

    except socket.timeout:
        return {
            "verdict": "TIMEOUT",
            "working": False,
            "possible": False,
            "alive": False,
            "status": "TIMEOUT",
            "http_code": None,
            "title": "",
            "final_url": url,
            "response_time": None,
            "score": 0,
            "error": "Connection timed out",
        }

    except URLError as e:
        reason = str(e.reason)

        if "timed out" in reason.lower():
            status = "TIMEOUT"
        elif "connection refused" in reason.lower():
            status = "CONNECTION_REFUSED"
        else:
            status = "CONNECTION_FAIL"

        return {
            "verdict": status,
            "working": False,
            "possible": False,
            "alive": False,
            "status": status,
            "http_code": None,
            "title": "",
            "final_url": url,
            "response_time": None,
            "score": 0,
            "error": reason,
        }

    except Exception as e:
        return {
            "verdict": "ERROR",
            "working": False,
            "possible": False,
            "alive": False,
            "status": "ERROR",
            "http_code": None,
            "title": "",
            "final_url": url,
            "response_time": None,
            "score": 0,
            "error": str(e),
        }


def check_domain(host: str, domain: str):
    result = {
        "domain": domain,
        "ip": None,
        "verdict": "UNKNOWN",
        "working": False,
        "possible": False,
        "alive": False,
        "status": "UNKNOWN",
        "http_code": None,
        "title": "",
        "final_url": None,
        "response_time": None,
        "score": 0,
        "error": None,
    }

    dns_ok, ip = dns_check(domain)

    if not dns_ok:
        result["verdict"] = "DNS_FAIL"
        result["status"] = "DNS_FAIL"
        result["error"] = "Domain does not resolve"
        return result

    result["ip"] = ip

    last_result = None

    for url in [f"https://{domain}", f"http://{domain}"]:
        checked = http_check(host, domain, url)
        last_result = checked
        result.update(checked)

        if checked["working"] or checked["possible"]:
            return result

        if checked["verdict"] in [
            "PARKED",
            "PLACEHOLDER",
            "BLOCKED",
            "LOW_CONFIDENCE",
            "EMPTY",
            "HTTP_ERROR",
        ]:
            return result

    if last_result:
        result.update(last_result)

    return result


def print_real(result):
    title = result["title"][:70] if result["title"] else "(no title)"
    print(
        f"[REAL]     {result['domain']:<30} "
        f"{result['http_code']}  "
        f"{result['response_time']}s  "
        f"score={result['score']}  "
        f"{title}"
    )


def print_possible(result):
    title = result["title"][:70] if result["title"] else "(no title)"
    print(
        f"[POSSIBLE] {result['domain']:<30} "
        f"{result['http_code']}  "
        f"{result['response_time']}s  "
        f"score={result['score']}  "
        f"{title}"
    )


def print_rejected(result):
    print(
        f"[REJECTED] {result['domain']:<30} "
        f"{result['verdict']:<16} "
        f"{result['error']}"
    )



def clear_progress_line():
    print("\r" + " " * min(term_width(), 140) + "\r", end="", flush=True)


def print_progress(completed: int, total: int, real_count: int, possible_count: int, rejected_count: int, latest: str = ""):
    if total <= 0:
        return

    percent = completed / total
    width = min(PROGRESS_WIDTH, max(18, term_width() - 72))
    filled = int(width * percent)
    bar = c("█" * filled, CYAN) + c("░" * (width - filled), GRAY)
    latest = clip(latest, 24)

    line = (
        f"\r{c('[SCAN]', BLUE)} [{bar}] "
        f"{completed:>3}/{total:<3} "
        f"{percent * 100:5.1f}%  "
        f"{c('real', GREEN)}:{real_count:<2} "
        f"{c('maybe', YELLOW)}:{possible_count:<2} "
        f"{c('dead', GRAY)}:{rejected_count:<2} "
        f"{c(latest, GRAY)}"
    )

    print(line, end="", flush=True)


def save_lines(path: Path, rows):
    lines = []

    for r in rows:
        title = r["title"] if r["title"] else ""
        final_url = r["final_url"] if r["final_url"] else ""
        lines.append(f"{r['domain']} | {r['verdict']} | score={r['score']} | {title} | {final_url}")

    path.write_text("\n".join(lines), encoding="utf-8")



def main():
    print_banner()
    raw_host = input(f"{c('Host', BOLD)} > ")

    host = clean_host(raw_host)

    if not host:
        print(c("[!] Invalid host.", RED))
        return

    tlds = load_tlds()

    if not tlds:
        print(c("[!] No TLDs found in Targets.txt", RED))
        return

    domains = [f"{host}.{tld}" for tld in tlds]

    print()
    print(c("SCAN CONFIG", BOLD))
    hr()
    print_kv("host", c(host, CYAN))
    print_kv("tlds", len(domains))
    print_kv("threads", THREADS)
    print_kv("timeout", f"{TIMEOUT}s")
    print_kv("filters", "parked / placeholder / registrar / low-content")
    print()

    results = []
    real = []
    possible = []
    rejected = []
    completed = 0
    total = len(domains)
    started = time.time()

    print_progress(completed, total, len(real), len(possible), len(rejected), "starting")

    with ThreadPoolExecutor(max_workers=THREADS) as executor:
        jobs = {
            executor.submit(check_domain, host, domain): domain
            for domain in domains
        }

        for job in as_completed(jobs):
            result = job.result()
            results.append(result)
            completed += 1

            if result["working"]:
                real.append(result)
            elif result["possible"]:
                possible.append(result)
            else:
                rejected.append(result)

            latest = f"{result['domain']}:{result['verdict']}"
            print_progress(completed, total, len(real), len(possible), len(rejected), latest)

    clear_progress_line()

    elapsed = round(time.time() - started, 2)

    results = sorted(results, key=lambda x: x["domain"])
    real = sorted(real, key=lambda x: (-x["score"], x["domain"]))
    possible = sorted(possible, key=lambda x: (-x["score"], x["domain"]))
    rejected = sorted(rejected, key=lambda x: x["domain"])

    RESULTS_FILE.write_text(
        json.dumps(results, indent=2),
        encoding="utf-8"
    )

    save_lines(REAL_FILE, real)
    save_lines(POSSIBLE_FILE, possible)
    save_lines(REJECTED_FILE, rejected)

    print(c("DONE", GREEN + BOLD))
    hr()
    print_kv("time", f"{elapsed}s")
    print_kv("real", c(len(real), GREEN))
    print_kv("possible", c(len(possible), YELLOW))
    print_kv("rejected", c(len(rejected), GRAY))

    print_result_table(f"REAL SITES ({len(real)})", real, GREEN)
    print_result_table(f"POSSIBLE SITES ({len(possible)})", possible, YELLOW)
    print_saved_files()



if __name__ == "__main__":
    main()