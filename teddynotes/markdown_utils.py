# SPDX-FileCopyrightText: 2026 Mohammed Asif Ali Rizvan
# SPDX-License-Identifier: GPL-3.0-or-later

import html
import re
import time
from typing import Dict, List, Optional, Tuple

# ==============================================================================
# Comprehensive Standard Markdown Emoji Map
# ==============================================================================
EMOJI_MAP: Dict[str, str] = {
    ":joy:": "😂",
    ":smile:": "😄",
    ":grinning:": "😀",
    ":smiley:": "😃",
    ":laughing:": "😆",
    ":innocent:": "😇",
    ":wink:": "😉",
    ":blush:": "😊",
    ":slightly_smiling_face:": "🙂",
    ":upside_down_face:": "🙃",
    ":relaxed:": "☺️",
    ":yum:": "😋",
    ":relieved:": "😌",
    ":heart_eyes:": "😍",
    ":kissing_heart:": "😘",
    ":kissing:": "😗",
    ":kissing_smiling_eyes:": "😙",
    ":kissing_closed_eyes:": "😚",
    ":stuck_out_tongue_winking_eye:": "😜",
    ":stuck_out_tongue_closed_eyes:": "😝",
    ":stuck_out_tongue:": "😛",
    ":money_mouth_face:": "🤑",
    ":nerd_face:": "🤓",
    ":sunglasses:": "😎",
    ":clown_face:": "🤡",
    ":cowboy_hat_face:": "🤠",
    ":hugs:": "🤗",
    ":smirk:": "😏",
    ":neutral_face:": "😐",
    ":expressionless:": "😑",
    ":unamused:": "😒",
    ":rolling_eyes:": "🙄",
    ":thinking:": "🤔",
    ":lying_face:": "🤥",
    ":flushed:": "😳",
    ":disappointed:": "😞",
    ":worried:": "😟",
    ":angry:": "😠",
    ":rage:": "😡",
    ":pensive:": "😔",
    ":confused:": "😕",
    ":slight_frown:": "🙁",
    ":frowning_face:": "☹️",
    ":persevere:": "😣",
    ":confounded:": "😖",
    ":tired_face:": "😫",
    ":weary:": "😩",
    ":triumph:": "😤",
    ":open_mouth:": "😮",
    ":scream:": "😱",
    ":fearful:": "😨",
    ":cold_sweat:": "😰",
    ":hushed:": "😯",
    ":frowning:": "😦",
    ":anguished:": "😧",
    ":cry:": "😢",
    ":disappointed_relieved:": "😥",
    ":drooling_face:": "🤤",
    ":sleepy:": "😪",
    ":sweat:": "😓",
    ":sob:": "😭",
    ":dizzy_face:": "😵",
    ":astonished:": "😲",
    ":zipper_mouth_face:": "🤐",
    ":nauseated_face:": "🤢",
    ":sneezing_face:": "🤧",
    ":mask:": "😷",
    ":face_with_thermometer:": "🤒",
    ":face_with_head_bandage:": "🤕",
    ":sleeping:": "😴",
    ":zzz:": "💤",
    ":poop:": "💩",
    ":fire:": "🔥",
    ":star:": "⭐",
    ":sparkles:": "✨",
    ":zap:": "⚡",
    ":boom:": "💥",
    ":collision:": "💥",
    ":tada:": "🎉",
    ":balloon:": "🎈",
    ":rocket:": "🚀",
    ":check:": "✓",
    ":white_check_mark:": "✅",
    ":heavy_check_mark:": "✔️",
    ":x:": "❌",
    ":negative_squared_cross_mark:": "❎",
    ":warning:": "⚠️",
    ":bulb:": "💡",
    ":heart:": "❤️",
    ":broken_heart:": "💔",
    ":purple_heart:": "💜",
    ":blue_heart:": "💙",
    ":green_heart:": "💚",
    ":yellow_heart:": "💛",
    ":black_heart:": "🖤",
    ":thumbsup:": "👍",
    ":+1:": "👍",
    ":thumbsdown:": "👎",
    ":-1:": "👎",
    ":clap:": "👏",
    ":wave:": "👋",
    ":pray:": "🙏",
    ":eyes:": "👀",
    ":100:": "💯",
    ":coffee:": "☕",
    ":tea:": "🍵",
    ":beer:": "🍺",
    ":pizza:": "🍕",
    ":apple:": "🍎",
    ":books:": "📚",
    ":book:": "📖",
    ":pencil:": "📝",
    ":pencil2:": "✏️",
    ":memo:": "📝",
    ":pushpin:": "📌",
    ":paperclip:": "📎",
    ":clock:": "⏰",
    ":alarm_clock:": "⏰",
    ":hourglass:": "⌛",
    ":calendar:": "📅",
    ":link:": "🔗",
    ":lock:": "🔒",
    ":unlock:": "🔓",
    ":key:": "🔑",
    ":bell:": "🔔",
    ":package:": "📦",
    ":computer:": "💻",
    ":phone:": "📱",
    ":camera:": "📷",
    ":magnifying_glass:": "🔍",
    ":wrench:": "🔧",
    ":hammer:": "🔨",
    ":gear:": "⚙️",
    ":bug:": "🐛",
    ":shield:": "🛡️",
    ":trophy:": "🏆",
    ":medal:": "🏅",
    ":crown:": "👑",
    ":diamond:": "💎",
    ":gem:": "💎",
    ":earth_americas:": "🌎",
    ":earth_africa:": "🌍",
    ":earth_asia:": "🌏",
    ":sun:": "☀️",
    ":moon:": "🌙",
    ":cloud:": "☁️",
    ":rainbow:": "🌈",
}

# Pre-compiled regular expressions for high performance

# check_has_todo
RE_TODO_BRACKETS = re.compile(r'\[[ xX]\]')
RE_TODO_STILO_TASK = re.compile(r'class=["\']stilo-task')
RE_TODO_STILO_CB = re.compile(r'class=["\']stilo-checkbox')
RE_TODO_MD = re.compile(r'^[-*+]\s+\[[ xX]\]', re.MULTILINE)
RE_TODO_INPUT_CB = re.compile(r'<input[^>]*type=["\']checkbox["\']', re.IGNORECASE)

# check_has_list
RE_LIST_MD_BULLET = re.compile(r'^\s*[-*+]\s+(?!\[[ xX]\])', re.MULTILINE)
RE_LIST_MD_NUMBER = re.compile(r'^\s*\d+\.\s+', re.MULTILINE)
RE_LIST_HTML = re.compile(r'<ul\b|<ol\b|stilo-list|stilo-numbered-list', re.IGNORECASE)

# strip_markdown
RE_HTML_TAGS = re.compile(r'<[^>]+>')
RE_HEADINGS = re.compile(r'#+\s*')
RE_HEADING_ID_TAG = re.compile(r'\s*\{#[^}]+\}')
RE_TASK_BOXES = re.compile(r'[-*+]\s+\[[ xX]\]\s*')
RE_LIST_BULLETS = re.compile(r'^[-*+]\s+', re.MULTILINE)
RE_LIST_NUMBERS = re.compile(r'^\d+\.\s+', re.MULTILINE)
RE_BLOCKQUOTES = re.compile(r'>+\s*')
RE_DIVIDERS = re.compile(r'(?:---|\*\*\*|___|- - -|\* \* \*|_ _ _)')
RE_CODE_FENCES = re.compile(r'(?:```|~~~).*?(?:```|~~~)', re.DOTALL)
RE_INLINE_CODE = re.compile(r'`([^`]+)`')
RE_IMAGES = re.compile(r'!\[([^\]]*)\]\([^)]+\)')
RE_LINKS = re.compile(r'\[([^\]]+)\]\([^)]+\)')
RE_AUTOLINKS = re.compile(r'<([^>]+)>')
RE_BOLD_ITALIC = re.compile(r'\*{1,3}([^*]+)\*{1,3}')
RE_UNDERSCORE = re.compile(r'_{1,3}([^_]+)_{1,3}')
RE_STRIKE = re.compile(r'~~([^~]+)~~')
RE_SUB = re.compile(r'(?<!~)~([^~\s\n]+)~(?!~)')
RE_SUP = re.compile(r'\^([^\^\s\n]+)\^')
RE_HIGHLIGHT = re.compile(r'==([^=]+)==')
RE_FOOTNOTE_REF = re.compile(r'\[\^[^\]]+\]')
RE_DEF_COLON = re.compile(r'^:\s+', re.MULTILINE)
RE_STRAY_SYMBOLS = re.compile(r'[*_~`#^]')
RE_WHITESPACE = re.compile(r'\s+')

# extract_title_and_excerpt
RE_H1_TAG = re.compile(r'<h1[^>]*>(.*?)</h1>', re.DOTALL)
RE_DIV_TAG = re.compile(r'<div[^>]*>')
RE_P_TAG = re.compile(r'<p[^>]*>')
RE_BR_TAG = re.compile(r'<br\s*/?>')

# CommonMark ASCII punctuation characters (Section 2.1 & 2.4)
ASCII_PUNCTUATION_STR = r"""!"#$%&'()*+,-./:;<=>?@[\]^_`{|}~"""
ASCII_PUNCTUATION_CHARS = set(ASCII_PUNCTUATION_STR)
RE_BACKSLASH_BEFORE_PUNCT = re.compile(r'\\(?=[' + re.escape(ASCII_PUNCTUATION_STR) + r']|@@STILO_)')

# markdown_to_html inline formatting
RE_MD_EMOJI = re.compile(r':([a-zA-Z0-9_\-+]+):')
RE_MD_AUTOLINK_URL = re.compile(r'&lt;(https?://[^&>\s]+)&gt;', re.IGNORECASE)
RE_MD_AUTOLINK_MAIL = re.compile(r'&lt;([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)&gt;', re.IGNORECASE)
RE_MD_FOOTNOTE_REF = re.compile(r'\[\^([a-zA-Z0-9_\-]+)\]')
RE_MD_IMAGE = re.compile(r'!\[([^\]]*)\]\(([^)\s]+)(?:\s+(?:["\']|&quot;)(.*?)(?:["\']|&quot;))?\)')
RE_MD_LINK = re.compile(r'\[([^\]]+)\]\(([^)\s]+)(?:\s+(?:["\']|&quot;)(.*?)(?:["\']|&quot;))?\)')
RE_MD_BOLD_ITALIC = re.compile(r'(?<!\*)\*\*\*(?!\*)([^\s\n](?:[^\n]*?[^\s\n])?)(?<!\*)\*\*\*(?!\*)')
RE_MD_BOLD_ITALIC_UNDER = re.compile(r'(?<!\w)(?<!_)___(?!_)([^_\s\n](?:[^\n]*?[^_\s\n])?)(?<!_)___(?!_)(?!\w)')
RE_MD_BOLD = re.compile(r'(?<!\*)\*\*(?!\*)([^\s\n](?:[^\n]*?[^\s\n])?)(?<!\*)\*\*(?!\*)')
RE_MD_BOLD_UNDER = re.compile(r'(?<!\w)(?<!_)__(?!_)([^_\s\n](?:[^\n]*?[^_\s\n])?)(?<!_)__(?!_)(?!\w)')
RE_MD_ITALIC_STAR = re.compile(r'(?<!\*)\*(?!\*)([^\s\n](?:[^\n]*?[^\s\n])?)(?<!\*)\*(?!\*)')
RE_MD_ITALIC_UNDER = re.compile(r'(?<!\w)(?<!_)_(?!_)([^_\s\n](?:[^\n]*?[^_\s\n])?)(?<!_)_(?!_)(?!\w)')
RE_MD_UNDERLINE = re.compile(r'&lt;u&gt;(.*?)&lt;/u&gt;', re.IGNORECASE)
RE_MD_INS = re.compile(r'&lt;ins&gt;(.*?)&lt;/ins&gt;', re.IGNORECASE)
RE_MD_PLUS_UNDER = re.compile(r'\+\+([^\+\n]+?)\+\+')
RE_MD_HIGHLIGHT = re.compile(r'==([^=\n]+?)==')
RE_MD_STRIKE = re.compile(r'~~([^~\n]+?)~~')
RE_MD_SUB = re.compile(r'(?<!~)~([^~\s\n]+?)~(?!~)')
RE_MD_SUP = re.compile(r'\^([^\^\s\n]+?)\^')
RE_MD_CODE = re.compile(r'`([^`\n]+)`')

# markdown_to_html block formatting
RE_BLOCK_CODE_FENCE = re.compile(r'^(?:```|~~~)(\w*)\s*$')
RE_BLOCK_TABLE_ROW = re.compile(r'^\|(.+)\|$')
RE_BLOCK_TABLE_SEP = re.compile(r'^[-: ]+$')
RE_BLOCK_HR = re.compile(r'^(?:---|\*\*\*|___|- - -|\* \* \*|_ _ _)\s*$')
RE_BLOCK_TODO = re.compile(r'^[-*+]\s+\[([ xX])\]\s*(.*)')
RE_BLOCK_UL = re.compile(r'^[-*+]\s+(.*)')
RE_BLOCK_OL = re.compile(r'^\d+[.)]\s+(.*)')
RE_BLOCK_FOOTNOTE_DEF = re.compile(r'^\[\^([a-zA-Z0-9_\-]+)\]:\s*(.*)')
RE_BLOCK_DEF_LIST = re.compile(r'^:\s+(.*)')
RE_HEADING_ID_IN_TEXT = re.compile(r'\s*\{#([a-zA-Z0-9_\-]+)\}\s*$')

# html_to_markdown
RE_HTM_TASK = re.compile(
    r'<div class="stilo-task[^"]*"[^>]*>\s*<input[^>]*type="checkbox"([^>]*)>\s*<span[^>]*>(.*?)</span>\s*</div>',
    re.DOTALL
)
RE_HTM_H_ID = re.compile(r'<h([1-6])[^>]*id=["\']([^"\']+)["\'][^>]*>(.*?)</h\1>', re.DOTALL)
RE_HTM_H_PLAIN = re.compile(r'<h([1-6])[^>]*>(.*?)</h\1>', re.DOTALL)
RE_HTM_HR = re.compile(r'<hr[^>]*>')
RE_HTM_CODE_LANG = re.compile(r'<pre[^>]*data-lang=["\'](.*?)["\'][^>]*><code[^>]*>(.*?)</code></pre>', re.DOTALL)
RE_HTM_CODE_NO_LANG = re.compile(r'<pre[^>]*><code[^>]*>(.*?)</code></pre>', re.DOTALL)
RE_HTM_FOOTNOTE_REF = re.compile(r'<sup[^>]*class=["\'][^"\']*stilo-footnote-ref[^"\']*["\'][^>]*><a[^>]*href=["\']#fn-([^"\']+)["\'][^>]*>.*?</a></sup>', re.DOTALL)
RE_HTM_FOOTNOTES_SECTION = re.compile(r'<section[^>]*class=["\'][^"\']*stilo-footnotes[^"\']*["\'][^>]*>.*?</section>', re.DOTALL)
RE_HTM_DL = re.compile(r'<dl[^>]*>(.*?)</dl>', re.DOTALL)
RE_HTM_DT = re.compile(r'<dt[^>]*>(.*?)</dt>', re.DOTALL)
RE_HTM_DD = re.compile(r'<dd[^>]*>(.*?)</dd>', re.DOTALL)
RE_HTM_TABLE = re.compile(r'<table[^>]*>.*?</table>', re.DOTALL)
RE_HTM_TH = re.compile(r'<th([^>]*)>(.*?)</th>', re.DOTALL)
RE_HTM_TR = re.compile(r'<tr[^>]*>(.*?)</tr>', re.DOTALL)
RE_HTM_TD = re.compile(r'<td([^>]*)>(.*?)</td>', re.DOTALL)
RE_HTM_LI = re.compile(r'<li[^>]*>(.*?)</li>', re.DOTALL)
RE_HTM_UL_START = re.compile(r'<ul[^>]*>')
RE_HTM_OL_START = re.compile(r'<ol[^>]*>')
RE_HTM_IMG_WRAPPER = re.compile(
    r'<div[^>]*class=["\'][^"\']*stilo-img-wrapper[^"\']*["\'][^>]*>.*?<img[^>]+>.*?</div>',
    re.DOTALL
)
RE_HTM_STANDALONE_IMG = re.compile(r'<img[^>]+>', re.DOTALL)
RE_HTM_LINK = re.compile(r'<a[^>]+href=["\']([^"\']+)["\'](?:[^>]*title=["\']([^"\']+)["\'])?[^>]*>(.*?)</a>', re.DOTALL)

RE_HTM_STRONG_EM = re.compile(r'<strong[^>]*><em>(.*?)</em></strong>', re.DOTALL)
RE_HTM_STRONG = re.compile(r'<strong[^>]*>(.*?)</strong>', re.DOTALL)
RE_HTM_B = re.compile(r'<b\b[^>]*>(.*?)</b>', re.DOTALL)
RE_HTM_EM = re.compile(r'<em[^>]*>(.*?)</em>', re.DOTALL)
RE_HTM_I = re.compile(r'<i\b[^>]*>(.*?)</i>', re.DOTALL)
RE_HTM_U = re.compile(r'<u\b[^>]*>(.*?)</u>', re.DOTALL)
RE_HTM_INS = re.compile(r'<ins\b[^>]*>(.*?)</ins>', re.DOTALL)
RE_HTM_DEL = re.compile(r'<(?:del|s|strike)\b[^>]*>(.*?)</(?:del|s|strike)>', re.DOTALL)
RE_HTM_MARK = re.compile(r'<mark\b[^>]*>(.*?)</mark>', re.DOTALL)
RE_HTM_SUB = re.compile(r'<sub\b[^>]*>(.*?)</sub>', re.DOTALL)
RE_HTM_SUP = re.compile(r'<sup\b[^>]*>(.*?)</sup>', re.DOTALL)
RE_HTM_CODE = re.compile(r'<code\b[^>]*>(.*?)</code>', re.DOTALL)

RE_HTM_DIV_BR = re.compile(r'<div[^>]*><br[^>]*></div>')
RE_HTM_DIV = re.compile(r'<div[^>]*>(.*?)</div>', re.DOTALL)
RE_HTM_P = re.compile(r'<p[^>]*>(.*?)</p>', re.DOTALL)
RE_HTM_BR = re.compile(r'<br[^>]*>')
RE_HTM_MULTI_NEWLINES = re.compile(r'\n{3,}')

# Symbol Mappings: #tag, @mention, [[Wiki Link]], ##Category
RE_TAG_EXTRACT = re.compile(r'(?<![#\w])#([a-zA-Z0-9_-]+(?:\\ [a-zA-Z0-9_-]+)*)(?![#\w])')
RE_CAT_HASH = re.compile(r'(?<!#)##([a-zA-Z0-9_\-]+(?:/[a-zA-Z0-9_\-]+)*)')
RE_CAT_SLASH = re.compile(r'(?:^|(?<=\s))/([a-zA-Z0-9_\-]+(?:/[a-zA-Z0-9_\-]+)*)(?=$|[\s.,;:!?])')
RE_MENTION_EXTRACT = re.compile(r'(?<![\w@])@([a-zA-Z0-9_\.\-]+)(?![@\w])')
RE_WIKI_LINK = re.compile(r'\[\[([^\]\n]+)\]\]')

RE_HTM_TAG = re.compile(r'<span[^>]*class=["\'][^"\']*stilo-tag[^"\']*["\'][^>]*data-tag=["\']([^"\']+)["\'][^>]*>.*?</span>', re.DOTALL)
RE_HTM_MENTION = re.compile(r'<span[^>]*class=["\'][^"\']*stilo-mention[^"\']*["\'][^>]*data-mention=["\']([^"\']+)["\'][^>]*>.*?</span>', re.DOTALL)
RE_HTM_WIKI = re.compile(r'<a[^>]*class=["\'][^"\']*stilo-wiki-link[^"\']*["\'][^>]*data-note-title=["\']([^"\']*)["\'][^>]*data-note-heading=["\']([^"\']*)["\'][^>]*>(.*?)</a>', re.DOTALL)
RE_HTM_CAT_BADGE = re.compile(r'<span[^>]*class=["\'][^"\']*stilo-category-badge[^"\']*["\'][^>]*data-category=["\']([^"\']+)["\'][^>]*>.*?</span>', re.DOTALL)
RE_MD_LINK_ONLY = re.compile(r'(?<!\!)\[([^\]]+)\]\(([^)\s]+)(?:\s+(?:["\']|&quot;)(.*?)(?:["\']|&quot;))?\)')
RE_LINK_URL = re.compile(r'https?://[^\s<>"\'`]+', re.IGNORECASE)

MD_SPECIAL_CHARS = set("#*_`[<~=-+:^@/")


def format_relative_date(timestamp: float) -> str:
    """Return a human-friendly relative date string."""
    if not timestamp:
        return "Unknown"

    now = time.time()
    diff = max(0, int(now - timestamp))

    if diff < 60:
        return "Just now"
    elif diff < 3600:
        mins = max(1, diff // 60)
        return f"{mins}m ago"
    elif diff < 86400:
        hours = diff // 3600
        return f"{hours}h ago"
    elif diff < 172800:
        return "Yesterday"
    elif diff < 604800:
        days = diff // 86400
        return f"{days}d ago"
    else:
        t = time.localtime(timestamp)
        now_t = time.localtime(now)
        if t.tm_year == now_t.tm_year:
            return time.strftime("%b %d", t)
        else:
            return time.strftime("%b %d, %Y", t)


def check_has_todo(content: str) -> bool:
    """Check if content has todo checklist items."""
    if not content:
        return False
    return bool(
        RE_TODO_BRACKETS.search(content)
        or RE_TODO_STILO_TASK.search(content)
        or RE_TODO_STILO_CB.search(content)
        or RE_TODO_MD.search(content)
        or RE_TODO_INPUT_CB.search(content)
    )


def check_has_list(content: str) -> bool:
    """Check if content contains a bullet list (*, -, +) or numbered list (1., etc.)."""
    if not content:
        return False
    return bool(
        RE_LIST_MD_BULLET.search(content)
        or RE_LIST_MD_NUMBER.search(content)
        or RE_LIST_HTML.search(content)
    )


def check_has_link(content: str) -> bool:
    """Check if content contains any links (internal wiki links or external URLs)."""
    if not content:
        return False
    return bool(
        RE_WIKI_LINK.search(content)
        or RE_MD_LINK_ONLY.search(content)
        or RE_HTM_LINK.search(content)
        or RE_HTM_WIKI.search(content)
        or "teddy-note://" in content
        or "stilo-note://" in content
        or RE_LINK_URL.search(content)
    )


def extract_tags(text: str) -> List[str]:
    """Extract all #tags from markdown/HTML text, ignoring headings and code blocks."""
    if not text:
        return []
    seen = set()
    result = []
    # Check for HTML tag badges first: <span class="stilo-tag" data-tag="...">
    for t in RE_HTM_TAG.findall(text):
        tag = t.strip().lstrip("#").replace("\\ ", " ").lower()
        if tag and tag not in seen:
            seen.add(tag)
            result.append(tag)

    # Exclude badge display text after recording data-tag, so a multiword badge
    # such as "#a and b" does not also create a second "#a" tag.
    clean = RE_HTM_TAG.sub(" ", text)
    clean = re.sub(r'```[\s\S]*?```', '', text)
    clean = re.sub(r'`[^`\n]+`', '', clean)
    clean = RE_HTML_TAGS.sub(' ', clean)
    matches = RE_TAG_EXTRACT.findall(clean)
    for m in matches:
        tag = m.strip().lstrip("#").replace("\\ ", " ").lower()
        if tag and tag not in seen:
            seen.add(tag)
            result.append(tag)
    return result


def extract_categories(text: str) -> List[str]:
    """Extract category declarations such as ##Category/Sub or /Category/Sub or HTML badges."""
    if not text:
        return []
    seen = set()
    result = []
    # Check for HTML category badges first: <span class="stilo-category-badge" data-category="...">
    for c in RE_HTM_CAT_BADGE.findall(text):
        clean_c = c.strip()
        if clean_c and clean_c.lower() != "uncategorized" and clean_c not in seen:
            seen.add(clean_c)
            result.append(clean_c)

    clean = re.sub(r'```[\s\S]*?```', '', text)
    clean = re.sub(r'`[^`\n]+`', '', clean)
    clean = RE_HTML_TAGS.sub(' ', clean)
    matches = []
    for m in RE_CAT_HASH.findall(clean):
        matches.append(m.strip())
    for m in RE_CAT_SLASH.findall(clean):
        matches.append(m.strip())
    for c in matches:
        if c and c.lower() != "uncategorized" and c not in seen:
            seen.add(c)
            result.append(c)
    return result


def extract_note_links(text: str) -> List[str]:
    """Extract internal note link titles [[Note Title]]."""
    if not text:
        return []
    clean = re.sub(r'```[\s\S]*?```', '', text)
    clean = re.sub(r'`[^`\n]+`', '', clean)
    clean = RE_HTML_TAGS.sub(' ', clean)
    matches = RE_WIKI_LINK.findall(clean)
    seen = set()
    result = []
    for l in matches:
        link = l.strip()
        if link and link not in seen:
            seen.add(link)
            result.append(link)
    return result


def strip_markdown(text: str) -> str:
    """Clean plain text extraction from Markdown/HTML."""
    if not text:
        return ""
    if not any(c in MD_SPECIAL_CHARS for c in text):
        return text.strip()

    s = text.replace('\u200b', '')
    s = RE_HTML_TAGS.sub(' ', s)
    s = RE_HEADINGS.sub('', s)
    s = RE_HEADING_ID_TAG.sub('', s)
    s = RE_TASK_BOXES.sub('', s)
    s = RE_LIST_BULLETS.sub('', s)
    s = RE_LIST_NUMBERS.sub('', s)
    s = RE_BLOCKQUOTES.sub('', s)
    s = RE_DIVIDERS.sub('', s)
    def _plain_wiki(m):
        d = m.group(3)
        return d[2:-2] if d.startswith("[[") and d.endswith("]]") else d
    s = RE_HTM_WIKI.sub(_plain_wiki, s)
    s = RE_WIKI_LINK.sub(r'\1', s)
    s = RE_HTM_TAG.sub(lambda m: "#" + re.sub(r"\s+", lambda _space: "\\ ", m.group(1).strip()), s)
    s = RE_HTM_MENTION.sub(r'@\1', s)
    s = RE_HTM_CAT_BADGE.sub(r'\1', s)
    s = RE_CAT_HASH.sub(r'\1', s)
    s = RE_CODE_FENCES.sub('', s)
    s = RE_INLINE_CODE.sub(r'\1', s)
    s = RE_IMAGES.sub(r'\1', s)
    s = RE_LINKS.sub(r'\1', s)
    s = RE_AUTOLINKS.sub(r'\1', s)
    s = RE_BOLD_ITALIC.sub(r'\1', s)
    s = RE_UNDERSCORE.sub(r'\1', s)
    s = RE_STRIKE.sub(r'\1', s)
    s = RE_SUB.sub(r'\1', s)
    s = RE_SUP.sub(r'\1', s)
    s = RE_MD_PLUS_UNDER.sub(r'\1', s)
    s = RE_HIGHLIGHT.sub(r'\1', s)
    s = RE_FOOTNOTE_REF.sub('', s)
    s = RE_DEF_COLON.sub('', s)
    s = RE_STRAY_SYMBOLS.sub('', s)
    s = html.unescape(s)
    return RE_WHITESPACE.sub(' ', s).strip()


def extract_table_data(content: str) -> Optional[List[List[str]]]:
    """Extract rows from the first table in markdown or HTML content."""
    if not content:
        return None

    # 1. Try markdown table
    lines = content.splitlines()
    table_lines = []
    in_table = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("|") and stripped.endswith("|") and stripped.count("|") >= 2:
            table_lines.append(stripped)
            in_table = True
        elif in_table:
            break

    if len(table_lines) >= 2:
        parsed_rows = []
        for tl in table_lines:
            cells = [c.strip() for c in tl.strip("|").split("|")]
            # Skip separator row like | --- | :--- |
            if all(re.match(r'^:?-+:?$', c) for c in cells if c):
                continue
            if any(cells):
                parsed_rows.append(cells)

        if parsed_rows:
            return parsed_rows

    # 2. Try HTML table
    table_match = re.search(r'<table[^>]*>(.*?)</table>', content, flags=re.DOTALL | re.IGNORECASE)
    if table_match:
        html_table = table_match.group(1)
        tr_matches = re.findall(r'<tr[^>]*>(.*?)</tr>', html_table, flags=re.DOTALL | re.IGNORECASE)
        parsed_rows = []
        for tr in tr_matches:
            cells = re.findall(r'<(?:th|td)[^>]*>(.*?)</(?:th|td)>', tr, flags=re.DOTALL | re.IGNORECASE)
            clean_cells = [strip_markdown(c).strip() for c in cells]
            if any(clean_cells):
                parsed_rows.append(clean_cells)
        if parsed_rows:
            return parsed_rows

    return None


RE_UNTITLED_NOTE = re.compile(r"^Untitled Note(?:\s+\d+)?$", re.IGNORECASE)

def is_untitled_title(title: Optional[str]) -> bool:
    """Return True if title is empty or an untitled note pattern (Untitled, Untitled Note, Untitled Note 1, etc.)."""
    if not title:
        return True
    s = title.strip()
    if not s or s.lower() == "untitled":
        return True
    return bool(RE_UNTITLED_NOTE.match(s))


def extract_title_and_excerpt(markdown_text: str = "", html_text: str = "") -> Tuple[str, str]:
    """Extract first non-empty line as title, and subsequent text as excerpt."""
    title = "Untitled Note"
    excerpt = ""

    lines = []
    if markdown_text:
        # Strip images before taking title and excerpt lines so image markup doesn't become text
        clean_md = re.sub(r'!\[.*?\]\([^)]+\)', '', markdown_text)
        clean_md = re.sub(r'<div[^>]*class=["\'][^"\']*stilo-img-wrapper[^"\']*["\'][^>]*>.*?</div>', '', clean_md, flags=re.DOTALL | re.IGNORECASE)
        clean_md = re.sub(r'<img[^>]*>', '', clean_md, flags=re.DOTALL | re.IGNORECASE)
        clean_lines = []
        for l in clean_md.splitlines():
            st = l.strip()
            # Skip table separator lines
            cells = [c.strip() for c in st.strip("|").split("|")]
            if all(re.match(r'^:?-+:?$', c) for c in cells if c):
                continue
            if st:
                clean_lines.append(st)
        lines = clean_lines
        if not lines:
            # Fall back to original lines if note contains only images
            lines = [line.strip() for line in markdown_text.splitlines() if line.strip()]
    elif html_text:
        clean = RE_H1_TAG.sub(r'\1\n', html_text)
        clean = RE_DIV_TAG.sub('\n', clean)
        clean = RE_P_TAG.sub('\n', clean)
        clean = RE_BR_TAG.sub('\n', clean)
        clean = re.sub(r'<div[^>]*class=["\'][^"\']*stilo-img-wrapper[^"\']*["\'][^>]*>.*?</div>', '', clean, flags=re.DOTALL | re.IGNORECASE)
        clean = re.sub(r'<img[^>]*>', '', clean, flags=re.DOTALL | re.IGNORECASE)
        clean = RE_HTML_TAGS.sub(' ', clean)
        lines = [line.strip() for line in html.unescape(clean).splitlines() if line.strip()]
        if not lines:
            clean_fallback = RE_HTML_TAGS.sub(' ', html_text)
            lines = [line.strip() for line in html.unescape(clean_fallback).splitlines() if line.strip()]

    if lines:
        title = strip_markdown(lines[0]) or "Untitled Note"
        if len(lines) > 1:
            non_table_lines = [l for l in lines[1:] if not (l.startswith("|") and l.endswith("|"))]
            if non_table_lines:
                raw_excerpt = " ".join(non_table_lines[:4])
                excerpt = strip_markdown(raw_excerpt)[:160]
            else:
                excerpt = ""

    return title, excerpt


def compute_note_stats(content_html: str = "", content_markdown: str = "") -> dict:
    """Calculate word count, characters, paragraphs, and reading time from note content."""
    content_html = content_html or ""
    content_markdown = content_markdown or ""
    if not content_html and content_markdown:
        content_html = markdown_to_html(content_markdown)

    text = ""
    if content_html:
        clean = RE_H1_TAG.sub(r'\1\n', content_html)
        clean = re.sub(r'</?(?:div|p|br|li|tr|blockquote|h[1-6]|dl|dt|dd|section)[^>]*>', '\n', clean, flags=re.IGNORECASE)
        clean = RE_HTML_TAGS.sub('', clean)
        text = html.unescape(clean).replace('\u200b', '')

    words = len(text.split())
    chars = len(text)
    paragraphs = len([p for p in text.splitlines() if p.strip()])
    read_minutes = max(1, (words + 199) // 200)

    return {
        "words": words,
        "chars": chars,
        "paragraphs": paragraphs,
        "readTime": f"{read_minutes} min"
    }


def _format_md_image(match: re.Match) -> str:
    alt = match.group(1)
    src = match.group(2)
    title = match.group(3) if len(match.groups()) >= 3 and match.group(3) else ""
    title_attr = f' title="{html.escape(title)}"' if title else ""
    width_style = ""
    clean_alt = alt
    if "|" in alt:
        parts = alt.rsplit("|", 1)
        w_str = parts[1].strip()
        if w_str.endswith("px"):
            w_str = w_str[:-2].strip()
        if w_str.isdigit():
            width_style = f' style="width: {w_str}px;"'
            clean_alt = parts[0].strip()
    return f'<div class="stilo-img-wrapper"{width_style}><img src="{src}" alt="{clean_alt}"{title_attr} class="stilo-img"></div>'


def _format_md_link(match: re.Match) -> str:
    text = match.group(1)
    url = match.group(2)
    title = match.group(3) if len(match.groups()) >= 3 and match.group(3) else ""
    title_attr = f' title="{html.escape(title)}"' if title else ""
    return f'<a href="{url}"{title_attr} class="stilo-link" target="_blank">{text}</a>'


def markdown_to_html(md_text: str) -> str:
    """Convert Markdown text to Teddy rich HTML with full Basic and Extended syntax support."""
    if not md_text:
        return "<h1>Untitled Note</h1><div><br></div>"

    def tokenize_markdown_inline(raw_text: str):
        code_spans: List[str] = []
        escapes: List[str] = []
        out: List[str] = []
        n = len(raw_text)
        i = 0
        while i < n:
            if raw_text[i] == '\\':
                if i + 1 < n and raw_text[i + 1] in ASCII_PUNCTUATION_CHARS:
                    esc_char = raw_text[i + 1]
                    idx = len(escapes)
                    escapes.append(esc_char)
                    out.append(f"\x00ESC_{idx}\x00")
                    i += 2
                    continue
                else:
                    out.append('\\')
                    i += 1
                    continue
            if raw_text[i] == '`':
                bt_start = i
                while i < n and raw_text[i] == '`':
                    i += 1
                bt_len = i - bt_start
                fence = '`' * bt_len
                close_pos = raw_text.find(fence, i)
                if close_pos != -1:
                    code_content = raw_text[i:close_pos]
                    if len(code_content) >= 2 and code_content.startswith(' ') and code_content.endswith(' ') and not code_content.strip() == '':
                        code_content = code_content[1:-1]
                    idx = len(code_spans)
                    code_spans.append(code_content)
                    out.append(f"\x00CODE_{idx}\x00")
                    i = close_pos + bt_len
                    continue
                else:
                    out.append(fence)
                    continue
            out.append(raw_text[i])
            i += 1
        return "".join(out), code_spans, escapes

    def format_inline(text: str) -> str:
        s, code_spans, escapes = tokenize_markdown_inline(text)
        s = html.escape(s)

        # Autolinks: <https://...> and <email@...>
        s = RE_MD_AUTOLINK_URL.sub(r'<a href="\1" class="stilo-link" target="_blank">\1</a>', s)
        s = RE_MD_AUTOLINK_MAIL.sub(r'<a href="mailto:\1" class="stilo-link">\1</a>', s)

        # Footnote references: [^1]
        s = RE_MD_FOOTNOTE_REF.sub(r'<sup class="stilo-footnote-ref"><a href="#fn-\1" id="fnref-\1">[\1]</a></sup>', s)

        # Images & Links
        s = RE_MD_IMAGE.sub(_format_md_image, s)
        s = RE_MD_LINK.sub(_format_md_link, s)

        # Emphasis (Bold, Italic)
        s = RE_MD_BOLD_ITALIC.sub(r'<strong><em>\1</em></strong>', s)
        s = RE_MD_BOLD_ITALIC_UNDER.sub(r'<strong><em>\1</em></strong>', s)
        s = RE_MD_BOLD.sub(r'<strong>\1</strong>', s)
        s = RE_MD_BOLD_UNDER.sub(r'<strong>\1</strong>', s)
        s = RE_MD_ITALIC_STAR.sub(r'<em>\1</em>', s)
        s = RE_MD_ITALIC_UNDER.sub(r'<em>\1</em>', s)

        # Underline & Inserted
        s = RE_MD_UNDERLINE.sub(r'<u>\1</u>', s)
        s = RE_MD_INS.sub(r'<u>\1</u>', s)
        s = RE_MD_PLUS_UNDER.sub(r'<u>\1</u>', s)

        # Highlight & Strikethrough
        s = RE_MD_HIGHLIGHT.sub(r'<mark class="stilo-highlight">\1</mark>', s)
        s = RE_MD_STRIKE.sub(r'<del>\1</del>', s)

        # Subscript & Superscript
        s = RE_MD_SUB.sub(r'<sub>\1</sub>', s)
        s = RE_MD_SUP.sub(r'<sup>\1</sup>', s)

        # Emoji shortcodes (:joy: -> 😂)
        s = RE_MD_EMOJI.sub(lambda m: EMOJI_MAP.get(m.group(0), m.group(0)), s)

        # Internal Note Links: [[Note Title]], [[Note Title/Heading]], [[Note Title|alias]]
        def _wiki_link_replacer(m: re.Match) -> str:
            content = m.group(1)
            alias = ""
            if "|" in content:
                parts = content.split("|", 1)
                content = parts[0]
                alias = parts[1]
            title = content
            heading = ""
            if "/" in content:
                parts = content.split("/", 1)
                title = parts[0]
                heading = parts[1]
            display = alias if alias else m.group(1).strip()
            from urllib.parse import quote
            safe_title = quote(title.strip())
            safe_heading = quote(heading.strip())
            href = f"teddy-note://{safe_title}" + (f"#{safe_heading}" if heading else "")
            return f'<a href="{href}" class="stilo-wiki-link" data-note-title="{title.strip()}" data-note-heading="{heading.strip()}">{display}</a>'
            
        s = RE_WIKI_LINK.sub(_wiki_link_replacer, s)

        # Tags: #tag, including multiword names with escaped spaces.
        def _format_tag(match: re.Match) -> str:
            tag = match.group(1).replace("\\ ", " ")
            safe_tag = html.escape(tag, quote=True)
            return f'<span class="stilo-tag" data-tag="{safe_tag}">#{safe_tag}</span>'
        s = RE_TAG_EXTRACT.sub(_format_tag, s)

        # Mentions: @name
        s = RE_MENTION_EXTRACT.sub(r'<span class="stilo-mention" data-mention="\1">@\1</span>', s)

        # Categories: ##Category/Sub
        s = RE_CAT_HASH.sub(r'<span class="stilo-category-badge" data-category="\1">📁 \1</span>', s)

        # Unmask backslash escapes (CommonMark 2.4)
        def _unmask_esc(m: re.Match) -> str:
            idx = int(m.group(1))
            return html.escape(escapes[idx])
        s = re.sub(r'\x00ESC_(\d+)\x00', _unmask_esc, s)

        # Unmask code spans (CommonMark 6.1)
        def _unmask_code(m: re.Match) -> str:
            idx = int(m.group(1))
            return f'<code class="stilo-inline-code">{html.escape(code_spans[idx])}</code>'
        s = re.sub(r'\x00CODE_(\d+)\x00', _unmask_code, s)

        return s

    raw_lines = md_text.replace('\r\n', '\n').replace('\r', '\n').split('\n')
    html_lines = []

    in_ul = False
    in_ol = False
    in_code_block = False
    code_lang = ""
    code_lines: List[str] = []
    in_table = False
    table_rows: List[str] = []
    in_def_list = False
    footnotes: Dict[str, str] = {}

    def close_lists():
        nonlocal in_ul, in_ol
        res = []
        if in_ul:
            res.append("</ul>")
            in_ul = False
        if in_ol:
            res.append("</ol>")
            in_ol = False
        return "\n".join(res)

    def close_def_list():
        nonlocal in_def_list
        if in_def_list:
            in_def_list = False
            return "</dl>"
        return ""

    def close_table():
        nonlocal in_table, table_rows
        if not in_table or not table_rows:
            in_table = False
            table_rows = []
            return ""

        out = ['<table class="stilo-table">']
        is_first = True
        alignments: List[str] = []

        # Pre-extract column alignments from separator row
        for r in table_rows:
            raw_c = [c.strip() for c in r.split('|')[1:-1]]
            if raw_c and any(RE_BLOCK_TABLE_SEP.match(c) for c in raw_c) and all(RE_BLOCK_TABLE_SEP.match(c) for c in raw_c if c):
                for c in raw_c:
                    c_clean = c.strip()
                    if c_clean.startswith(':') and c_clean.endswith(':'):
                        alignments.append("center")
                    elif c_clean.endswith(':'):
                        alignments.append("right")
                    elif c_clean.startswith(':'):
                        alignments.append("left")
                    else:
                        alignments.append("left")
                break

        for row in table_rows:
            raw_cells = [c.strip() for c in row.split('|')[1:-1]]
            if not raw_cells:
                continue

            # Skip separator row in output
            if any(RE_BLOCK_TABLE_SEP.match(c) for c in raw_cells) and all(RE_BLOCK_TABLE_SEP.match(c) for c in raw_cells if c):
                continue

            if is_first:
                ths = []
                for i, c in enumerate(raw_cells):
                    align = alignments[i] if i < len(alignments) else "left"
                    style_attr = f' style="text-align: {align};"' if align != "left" else ""
                    ths.append(f'<th{style_attr}>{format_inline(c)}</th>')
                out.append('<thead><tr>' + ''.join(ths) + '</tr></thead><tbody>')
                is_first = False
            else:
                tds = []
                for i, c in enumerate(raw_cells):
                    align = alignments[i] if i < len(alignments) else "left"
                    style_attr = f' style="text-align: {align};"' if align != "left" else ""
                    tds.append(f'<td{style_attr}>{format_inline(c)}</td>')
                out.append('<tr>' + ''.join(tds) + '</tr>')

        out.append('</tbody></table>')
        in_table = False
        table_rows = []
        return "\n".join(out)

    num_lines = len(raw_lines)
    i = 0

    while i < num_lines:
        line = raw_lines[i]

        # 1. Code block fences (``` or ~~~)
        code_fence = RE_BLOCK_CODE_FENCE.match(line)
        if code_fence:
            if in_code_block:
                escaped_code = html.escape("\n".join(code_lines))
                lang_attr = f' data-lang="{code_lang}"' if code_lang else ''
                html_lines.append(f'<pre class="stilo-code-block"{lang_attr}><code>{escaped_code}\n</code></pre><div><br></div>')
                in_code_block = False
                code_lines = []
            else:
                html_lines.append(close_lists())
                html_lines.append(close_def_list())
                in_code_block = True
                code_lang = code_fence.group(1)
                code_lines = []
            i += 1
            continue

        if in_code_block:
            code_lines.append(line)
            i += 1
            continue

        # 2. Tables
        if RE_BLOCK_TABLE_ROW.match(line.strip()):
            html_lines.append(close_lists())
            html_lines.append(close_def_list())
            in_table = True
            table_rows.append(line.strip())
            i += 1
            continue
        elif in_table:
            html_lines.append(close_table())

        # 3. Footnote definitions: [^1]: text
        fn_match = RE_BLOCK_FOOTNOTE_DEF.match(line)
        if fn_match:
            html_lines.append(close_lists())
            html_lines.append(close_def_list())
            fn_id = fn_match.group(1)
            fn_content = fn_match.group(2)
            # Check indented continuation lines
            while i + 1 < num_lines and (raw_lines[i + 1].startswith("    ") or raw_lines[i + 1].startswith("\t")):
                i += 1
                fn_content += " " + raw_lines[i].strip()
            footnotes[fn_id] = fn_content
            i += 1
            continue

        # 4. Definition List item: ": definition"
        def_match = RE_BLOCK_DEF_LIST.match(line)
        if def_match:
            def_text = format_inline(def_match.group(1))
            if not in_def_list:
                # The preceding line (if non-empty) was the term
                term_text = ""
                if html_lines and html_lines[-1].startswith("<div>") and html_lines[-1].endswith("</div>"):
                    term_div = html_lines.pop()
                    term_text = term_div[5:-6]
                in_def_list = True
                html_lines.append('<dl class="stilo-dl">')
                if term_text:
                    html_lines.append(f'<dt>{term_text}</dt>')
            html_lines.append(f'<dd>{def_text}</dd>')
            i += 1
            continue
        elif in_def_list:
            html_lines.append(close_def_list())

        # 5. Empty line
        if not line.strip():
            html_lines.append(close_lists())
            html_lines.append("<div><br></div>")
            i += 1
            continue

        # 6. Setext Headings (Heading 1 === or Heading 2 ---)
        if i + 1 < num_lines and line.strip():
            next_line = raw_lines[i + 1].strip()
            if re.match(r'^===+\s*$', next_line):
                html_lines.append(close_lists())
                html_lines.append(f"<h1>{format_inline(line.strip())}</h1>")
                i += 2
                continue
            elif re.match(r'^---+\s*$', next_line) and not RE_BLOCK_HR.match(line):
                html_lines.append(close_lists())
                html_lines.append(f"<h2>{format_inline(line.strip())}</h2>")
                i += 2
                continue

        # 7. Atx Headings (# H1 to ###### H6 with optional {#custom-id})
        heading_level = 0
        stripped_line = line.lstrip(" ")
        leading_spaces = len(line) - len(stripped_line)
        if leading_spaces <= 3 and stripped_line.startswith("#"):
            stripped_hashes = stripped_line.lstrip("#")
            level = len(stripped_line) - len(stripped_hashes)
            if 1 <= level <= 6 and (stripped_hashes.startswith(" ") or stripped_hashes == ""):
                heading_level = level
                heading_content = stripped_hashes.strip()

        if heading_level > 0:
            html_lines.append(close_lists())
            id_attr = ""
            id_match = RE_HEADING_ID_IN_TEXT.search(heading_content)
            if id_match:
                id_attr = f' id="{id_match.group(1)}"'
                heading_content = heading_content[:id_match.start()].strip()
            # CommonMark Section 4.2: optional closing sequence of '#'s
            heading_content = re.sub(r'(?:^|\s+)#+\s*$', '', heading_content).strip()
            html_lines.append(f"<h{heading_level}{id_attr}>{format_inline(heading_content)}</h{heading_level}>")
            i += 1
            continue

        # 8. Horizontal Rule (---, ***, ___, - - -, * * *, _ _ _)
        if RE_BLOCK_HR.match(line):
            html_lines.append(close_lists())
            html_lines.append('<hr class="stilo-hr">')
            i += 1
            continue

        # 9. Todo Checklist: - [ ] or - [x] (also * and +)
        todo_match = RE_BLOCK_TODO.match(line)
        if todo_match:
            html_lines.append(close_lists())
            checked = todo_match.group(1).lower() == 'x'
            checked_attr = 'checked="checked"' if checked else ''
            done_class = ' completed' if checked else ''
            item_text = format_inline(todo_match.group(2))
            html_lines.append(
                f'<div class="stilo-task{done_class}">'
                f'<input type="checkbox" class="stilo-checkbox" {checked_attr}>'
                f'<span class="task-text">{item_text}</span>'
                f'</div>'
            )
            i += 1
            continue

        # 10. Blockquote (supports multi-line blockquotes and nesting: > and >> and >>>)
        if line.startswith(">"):
            html_lines.append(close_lists())
            q_lines = []
            while i < num_lines and raw_lines[i].startswith(">"):
                cur_line = raw_lines[i]
                q_hashes = len(cur_line) - len(cur_line.lstrip('>'))
                q_content = cur_line.lstrip('>').strip()
                q_html = format_inline(q_content)
                q_lines.append((q_hashes, q_html))
                i += 1

            if all(h == 1 for h, _ in q_lines):
                inner = "".join(f"<div>{html_part or '<br>'}</div>" for _, html_part in q_lines)
                html_lines.append(f'<blockquote class="stilo-quote">{inner}</blockquote>')
            else:
                for q_hashes, q_html in q_lines:
                    wrapped = f'<blockquote class="stilo-quote">{q_html or "<br>"}</blockquote>'
                    for _ in range(q_hashes - 1):
                        wrapped = f'<blockquote class="stilo-quote">{wrapped}</blockquote>'
                    html_lines.append(wrapped)
            continue

        # 11. Unordered list: - or * or +
        ul_match = RE_BLOCK_UL.match(line)
        if ul_match:
            if in_ol:
                html_lines.append("</ol>")
                in_ol = False
            if not in_ul:
                html_lines.append('<ul class="stilo-list">')
                in_ul = True
            html_lines.append(f"<li>{format_inline(ul_match.group(1))}</li>")
            i += 1
            continue

        # 12. Ordered list: 1.
        ol_match = RE_BLOCK_OL.match(line)
        if ol_match:
            if in_ul:
                html_lines.append("</ul>")
                in_ul = False
            if not in_ol:
                html_lines.append('<ol class="stilo-numbered-list">')
                in_ol = True
            html_lines.append(f"<li>{format_inline(ol_match.group(1))}</li>")
            i += 1
            continue

        # 13. Standalone Image line: ![alt](url)
        img_match = RE_MD_IMAGE.match(line.strip())
        if img_match:
            html_lines.append(close_lists())
            html_lines.append(_format_md_image(img_match))
            i += 1
            continue

        # 14. Regular paragraph/div with trailing line break support
        html_lines.append(close_lists())
        line_clean = line
        line_break = ""
        if line_clean.endswith("  "):
            line_clean = line_clean[:-2]
            line_break = "<br>"
        else:
            # Check trailing backslashes: odd number means hard line break (CommonMark 6.7)
            bs_match = re.search(r'(\\+)$', line_clean)
            if bs_match and len(bs_match.group(1)) % 2 == 1:
                line_clean = line_clean[:-1]
                line_break = "<br>"
        html_lines.append(f"<div>{format_inline(line_clean)}{line_break}</div>")
        i += 1

    if in_code_block:
        escaped_code = html.escape("\n".join(code_lines))
        html_lines.append(f'<pre class="stilo-code-block"><code>{escaped_code}\n</code></pre>')
    if in_table:
        html_lines.append(close_table())
    html_lines.append(close_lists())
    html_lines.append(close_def_list())

    # Append Footnotes section if any were collected
    if footnotes:
        fn_items = []
        for fn_id, fn_text in footnotes.items():
            formatted_text = format_inline(fn_text)
            fn_items.append(
                f'<li id="fn-{fn_id}">{formatted_text} <a href="#fnref-{fn_id}" class="stilo-footnote-backref" title="Jump back to footnote in text">&#8617;</a></li>'
            )
        html_lines.append(
            '<section class="stilo-footnotes">\n'
            '<hr class="stilo-footnotes-sep">\n'
            '<ol class="stilo-footnotes-list">\n'
            + "\n".join(fn_items) +
            '\n</ol>\n</section>'
        )

    return "\n".join(html_lines)


def html_to_markdown(html_content: str) -> str:
    """Convert Teddy rich HTML back to clean Markdown supporting Basic and Extended syntax."""
    if not html_content:
        return ""

    s = html_content.replace('\r\n', '\n').replace('\r', '\n')

    # 1. Convert Footnotes section and references
    fn_defs: List[str] = []

    def extract_footnote_defs(sec_match: re.Match) -> str:
        sec_html = sec_match.group(0)
        items = re.findall(r'<li[^>]*id=["\']fn-([^"\']+)["\'][^>]*>(.*?)</li>', sec_html, re.DOTALL)
        for fn_id, raw_content in items:
            clean_content = re.sub(r'<a[^>]*class=["\'][^"\']*stilo-footnote-backref[^"\']*["\'][^>]*>.*?</a>', '', raw_content, flags=re.DOTALL)
            clean_content = RE_HTML_TAGS.sub('', clean_content).strip()
            fn_defs.append(f"[^{fn_id}]: {clean_content}")
        return ""

    s = RE_HTM_FOOTNOTES_SECTION.sub(extract_footnote_defs, s)
    s = RE_HTM_FOOTNOTE_REF.sub(r'[^\1]', s)

    # 2. Convert Tasks
    def replace_task(m: re.Match) -> str:
        checked = 'checked' in m.group(1)
        text = RE_HTML_TAGS.sub('', m.group(2)).strip()
        mark = 'x' if checked else ' '
        return f"- [{mark}] {text}\n"

    s = RE_HTM_TASK.sub(replace_task, s)

    # 3. Convert Definition Lists
    def replace_dl(m: re.Match) -> str:
        dl_html = m.group(1)
        out = []
        parts = re.findall(r'<(dt|dd)[^>]*>(.*?)</\1>', dl_html, re.DOTALL)
        for tag, content in parts:
            clean_txt = RE_HTML_TAGS.sub('', content).strip()
            if tag == 'dt':
                out.append(f"\n{clean_txt}")
            else:
                out.append(f": {clean_txt}")
        return "\n".join(out) + "\n\n"

    s = RE_HTM_DL.sub(replace_dl, s)

    # 4. Convert Headings (1-6, with and without custom ID)
    def replace_heading_id(m: re.Match) -> str:
        lvl = int(m.group(1))
        h_id = m.group(2)
        txt = RE_HTML_TAGS.sub('', m.group(3)).strip()
        return f"{'#' * lvl} {txt} {{#{h_id}}}\n\n"

    def replace_heading_plain(m: re.Match) -> str:
        lvl = int(m.group(1))
        txt = RE_HTML_TAGS.sub('', m.group(2)).strip()
        return f"{'#' * lvl} {txt}\n\n"

    s = RE_HTM_H_ID.sub(replace_heading_id, s)
    s = RE_HTM_H_PLAIN.sub(replace_heading_plain, s)

    # 5. Convert Horizontal Rules
    s = RE_HTM_HR.sub('\n---\n\n', s)

    # 6. Convert Code Blocks
    def replace_code_block(m: re.Match) -> str:
        lang = m.group(1) or ""
        code = html.unescape(m.group(2)).rstrip('\n')
        return f"\n@@STILO_CB_START@@{lang}\n{code}\n@@STILO_CB_END@@\n\n"

    s = RE_HTM_CODE_LANG.sub(replace_code_block, s)
    s = RE_HTM_CODE_NO_LANG.sub(lambda m: f"\n@@STILO_CB_START@@\n{html.unescape(m.group(1)).rstrip(chr(10))}\n@@STILO_CB_END@@\n\n", s)

    # 7. Convert Blockquotes (recursively handles nesting)
    def _convert_blockquote_to_md(m: re.Match) -> str:
        inner = m.group(1)
        inner = re.sub(r'<br\s*/?>', '\n', inner)
        inner = re.sub(r'</?(?:div|p)[^>]*>', '\n', inner)
        clean_lines = [RE_HTML_TAGS.sub('', line).strip() for line in inner.splitlines()]
        clean_lines = [line for line in clean_lines if line]
        if not clean_lines:
            return "\n> \n\n"
        return "\n" + "\n".join(f"> {line}" for line in clean_lines) + "\n\n"

    while '<blockquote' in s:
        s = re.sub(r'<blockquote[^>]*>(.*?)</blockquote>', _convert_blockquote_to_md, s, flags=re.DOTALL)

    # 8. Convert Tables with Alignment
    def replace_table(m: re.Match) -> str:
        table_html = m.group(0)
        th_matches = RE_HTM_TH.findall(table_html)
        tr_matches = RE_HTM_TR.findall(table_html)

        def _clean_cell(raw_text: str) -> str:
            c = RE_HTM_STRONG_EM.sub(r'@@STILO_BI_START@@\1@@STILO_BI_END@@', raw_text)
            c = RE_HTM_STRONG.sub(r'@@STILO_B_START@@\1@@STILO_B_END@@', c)
            c = RE_HTM_B.sub(r'@@STILO_B_START@@\1@@STILO_B_END@@', c)
            c = RE_HTM_EM.sub(r'@@STILO_I_START@@\1@@STILO_I_END@@', c)
            c = RE_HTM_I.sub(r'@@STILO_I_START@@\1@@STILO_I_END@@', c)
            c = RE_HTM_U.sub(r'@@STILO_U_START@@\1@@STILO_U_END@@', c)
            c = RE_HTM_INS.sub(r'@@STILO_U_START@@\1@@STILO_U_END@@', c)
            c = RE_HTM_DEL.sub(r'@@STILO_DEL_START@@\1@@STILO_DEL_END@@', c)
            c = RE_HTM_MARK.sub(r'@@STILO_MARK_START@@\1@@STILO_MARK_END@@', c)
            c = RE_HTM_SUB.sub(r'@@STILO_SUB_START@@\1@@STILO_SUB_END@@', c)
            c = RE_HTM_SUP.sub(r'@@STILO_SUP_START@@\1@@STILO_SUP_END@@', c)
            c = RE_HTM_CODE.sub(r'@@STILO_CODE_START@@\1@@STILO_CODE_END@@', c)
            c = RE_HTML_TAGS.sub('', c)
            c = html.unescape(c)
            c = c.replace('\u200b', '').replace('\n', ' ').replace('\r', ' ')
            return c.strip()

        md_table = []
        align_seps = []

        if th_matches:
            clean_headers = []
            for attrs, h_content in th_matches:
                clean_headers.append(_clean_cell(h_content))
                # Detect alignment
                if 'text-align: center' in attrs or 'text-align:center' in attrs or 'align-center' in attrs:
                    align_seps.append(":---:")
                elif 'text-align: right' in attrs or 'text-align:right' in attrs or 'align-right' in attrs:
                    align_seps.append("---:")
                else:
                    align_seps.append(":---")

            # Fallback: if th lacked alignment, check first data row's td attributes
            if tr_matches and not any(a != ':---' for a in align_seps):
                first_tds = RE_HTM_TD.findall(tr_matches[0])
                if first_tds and len(first_tds) == len(align_seps):
                    for idx, (td_attrs, _) in enumerate(first_tds):
                        if 'text-align: center' in td_attrs or 'text-align:center' in td_attrs or 'align-center' in td_attrs:
                            align_seps[idx] = ":---:"
                        elif 'text-align: right' in td_attrs or 'text-align:right' in td_attrs or 'align-right' in td_attrs:
                            align_seps[idx] = "---:"

            md_table.append("| " + " | ".join(clean_headers) + " |")
            md_table.append("| " + " | ".join(align_seps) + " |")

        for r in tr_matches:
            td_matches = RE_HTM_TD.findall(r)
            if td_matches:
                clean_cells = [_clean_cell(content) for _, content in td_matches]
                md_table.append("| " + " | ".join(clean_cells) + " |")

        return "\n" + "\n".join(md_table) + "\n\n"

    s = RE_HTM_TABLE.sub(replace_table, s)

    # 9. Convert Lists
    def _replace_ol(m: re.Match) -> str:
        content = m.group(1)
        i = [0]
        def repl(m2: re.Match) -> str:
            i[0] += 1
            return f"{i[0]}. {m2.group(1)}\n"
        return "\n" + RE_HTM_LI.sub(repl, content) + "\n"

    def _replace_ul(m: re.Match) -> str:
        content = m.group(1)
        def repl(m2: re.Match) -> str:
            return f"- {m2.group(1)}\n"
        return "\n" + RE_HTM_LI.sub(repl, content) + "\n"

    s = re.sub(r'<ol[^>]*>(.*?)</ol>', _replace_ol, s, flags=re.DOTALL)
    s = re.sub(r'<ul[^>]*>(.*?)</ul>', _replace_ul, s, flags=re.DOTALL)
    s = RE_HTM_LI.sub(r'- \1\n', s)

    # 10. Convert Images
    def _convert_img_wrapper_to_md(m: re.Match) -> str:
        wrapper_html = m.group(0)
        w_match = re.search(r'width:\s*(\d+)px', wrapper_html)
        width = w_match.group(1) if w_match else ""
        src_match = re.search(r'src=["\']([^"\']+)["\']', wrapper_html)
        alt_match = re.search(r'alt=["\']([^"\']*)["\']', wrapper_html)
        title_match = re.search(r'title=["\']([^"\']*)["\']', wrapper_html)
        src = src_match.group(1) if src_match else ""
        alt = alt_match.group(1) if alt_match else ""
        title = f' "{title_match.group(1)}"' if title_match else ""
        if not src:
            return ""
        if width:
            return f"![{alt}|{width}]({src}{title})\n"
        elif alt:
            return f"![{alt}]({src}{title})\n"
        else:
            return f"![]({src}{title})\n"

    def _convert_standalone_img_to_md(m: re.Match) -> str:
        img_html = m.group(0)
        w_match = re.search(r'width:\s*(\d+)px', img_html)
        width = w_match.group(1) if w_match else ""
        src_match = re.search(r'src=["\']([^"\']+)["\']', img_html)
        alt_match = re.search(r'alt=["\']([^"\']*)["\']', img_html)
        title_match = re.search(r'title=["\']([^"\']*)["\']', img_html)
        src = src_match.group(1) if src_match else ""
        alt = alt_match.group(1) if alt_match else ""
        title = f' "{title_match.group(1)}"' if title_match else ""
        if not src:
            return ""
        if width:
            return f"![{alt}|{width}]({src}{title})\n"
        elif alt:
            return f"![{alt}]({src}{title})\n"
        else:
            return f"![]({src}{title})\n"

    s = RE_HTM_IMG_WRAPPER.sub(_convert_img_wrapper_to_md, s)
    s = RE_HTM_STANDALONE_IMG.sub(_convert_standalone_img_to_md, s)

    # 10.5 Convert Wiki Links, Tags, Mentions, Category Badges
    def _html_to_md_wiki(m):
        title = m.group(1).strip()
        heading = m.group(2).strip()
        display = m.group(3).strip()
        if display.startswith("[[") and display.endswith("]]"):
            return display
        base = title
        if heading:
            base += f"/{heading}"
        if not display or display == base or display == title:
            return f"[[{base}]]"
        return f"[[{base}|{display}]]"
    s = RE_HTM_WIKI.sub(_html_to_md_wiki, s)
    s = RE_HTM_TAG.sub(lambda m: "#" + re.sub(r"\s+", lambda _space: "\\ ", m.group(1).strip()), s)
    s = RE_HTM_MENTION.sub(r'@\1', s)
    s = RE_HTM_CAT_BADGE.sub(r'##\1', s)

    # 11. Convert Links
    def _convert_link_to_md(m: re.Match) -> str:
        url = m.group(1)
        title = f' "{m.group(2)}"' if m.group(2) else ""
        text = RE_HTML_TAGS.sub('', m.group(3)).strip()
        return f"[{text}]({url}{title})"

    s = RE_HTM_LINK.sub(_convert_link_to_md, s)

    # 12. Inline Formatting
    s = RE_HTM_CODE.sub(lambda m: f'@@STILO_CODE_START@@{m.group(1)}@@STILO_CODE_END@@', s)
    s = RE_HTM_STRONG_EM.sub(lambda m: f'@@STILO_BI_START@@{m.group(1)}@@STILO_BI_END@@', s)
    s = RE_HTM_STRONG.sub(lambda m: f'@@STILO_B_START@@{m.group(1)}@@STILO_B_END@@', s)
    s = RE_HTM_B.sub(lambda m: f'@@STILO_B_START@@{m.group(1)}@@STILO_B_END@@', s)
    s = RE_HTM_EM.sub(lambda m: f'@@STILO_I_START@@{m.group(1)}@@STILO_I_END@@', s)
    s = RE_HTM_I.sub(lambda m: f'@@STILO_I_START@@{m.group(1)}@@STILO_I_END@@', s)
    s = RE_HTM_U.sub(r'@@STILO_U_START@@\1@@STILO_U_END@@', s)
    s = RE_HTM_INS.sub(r'@@STILO_U_START@@\1@@STILO_U_END@@', s)
    s = RE_HTM_DEL.sub(lambda m: f'@@STILO_DEL_START@@{m.group(1)}@@STILO_DEL_END@@', s)
    s = RE_HTM_MARK.sub(lambda m: f'@@STILO_MARK_START@@{m.group(1)}@@STILO_MARK_END@@', s)
    s = RE_HTM_SUB.sub(lambda m: f'@@STILO_SUB_START@@{m.group(1)}@@STILO_SUB_END@@', s)
    s = RE_HTM_SUP.sub(lambda m: f'@@STILO_SUP_START@@{m.group(1)}@@STILO_SUP_END@@', s)

    # Escape literal backslashes that precede punctuation or formatting markers
    s = RE_BACKSLASH_BEFORE_PUNCT.sub(r'\\\\', s)

    # In plain text outside protected tags, escape literal asterisks that would form delimiter runs (e.g. **/** or *foo*)
    def _esc_plain_asterisks(m: re.Match) -> str:
        return re.sub(r'(?<!\\)\*', r'@@STILO_ESC_STAR@@', m.group(0))
    s = re.sub(r'\*\*[^*\n@]+?\*\*', _esc_plain_asterisks, s)
    s = re.sub(r'(?<!\*)\*[^*\s\n@](?:[^*\n@]*?[^*\s\n@])?\*(?!\*)', _esc_plain_asterisks, s)

    # In plain text outside protected code, escape plain-text backticks
    s = re.sub(r'(?<!\\)`', r'@@STILO_ESC_TICK@@', s)

    # In plain text outside links, escape markdown link patterns [text](url)
    def _esc_plain_link(m: re.Match) -> str:
        return r'\[' + m.group(1) + r'](' + m.group(2) + ')'
    s = re.sub(r'(?<![!\\@])\[([^\]\n]+)\]\(([^)\s]+)\)', _esc_plain_link, s)

    s = s.replace('@@STILO_CB_START@@', '```').replace('@@STILO_CB_END@@', '```')
    s = s.replace('@@STILO_CODE_START@@', '`').replace('@@STILO_CODE_END@@', '`')
    s = s.replace('@@STILO_BI_START@@', '***').replace('@@STILO_BI_END@@', '***')
    s = s.replace('@@STILO_B_START@@', '**').replace('@@STILO_B_END@@', '**')
    s = s.replace('@@STILO_I_START@@', '*').replace('@@STILO_I_END@@', '*')
    s = s.replace('@@STILO_DEL_START@@', '~~').replace('@@STILO_DEL_END@@', '~~')
    s = s.replace('@@STILO_MARK_START@@', '==').replace('@@STILO_MARK_END@@', '==')
    s = s.replace('@@STILO_SUB_START@@', '~').replace('@@STILO_SUB_END@@', '~')
    s = s.replace('@@STILO_SUP_START@@', '^').replace('@@STILO_SUP_END@@', '^')
    s = s.replace('@@STILO_ESC_STAR@@', r'\*')
    s = s.replace('@@STILO_ESC_TICK@@', r'\`')

    # 13. Convert Paragraphs and Divs
    def _escape_plain_block_starts(m: re.Match) -> str:
        content = m.group(1)
        # Heading start: # H
        content = re.sub(r'^(\s{0,3})#(#{0,5}\s+)', r'\1\\#\2', content)
        # Blockquote start: > quote
        content = re.sub(r'^(\s{0,3})>\s*', r'\1\\> ', content)
        # Unordered list start: * item, - item, + item
        content = re.sub(r'^(\s*)([-*+])(\s+)', r'\1\\\2\3', content)
        # Ordered list start: 1. item
        content = re.sub(r'^(\s*)(\d+)\.(\s+)', r'\1\2\\.\3', content)
        return content + '\n'

    s = RE_HTM_DIV_BR.sub('\n\n', s)
    s = RE_HTM_DIV.sub(_escape_plain_block_starts, s)
    s = RE_HTM_P.sub(lambda m: _escape_plain_block_starts(m) + '\n', s)
    s = RE_HTM_BR.sub('\n', s)

    # 14. Strip Remaining Tags and Unescape
    s = RE_HTML_TAGS.sub('', s)
    s = html.unescape(s)
    s = s.replace('@@STILO_U_START@@', '<u>').replace('@@STILO_U_END@@', '</u>')
    s = s.replace('\u200b', '')

    # 15. Append Footnotes definitions at end
    if fn_defs:
        s += "\n\n" + "\n".join(fn_defs)

    # 16. Collapse Blank Lines
    s = RE_HTM_MULTI_NEWLINES.sub('\n\n', s)
    return s.strip()
