import re
from urllib.parse import quote


def slugify_title(title: str) -> str:
    """
    Create a lowercase, hyphenated, ASCII-only slug from a title.
    Removes punctuation and special characters.
    """
    # Replace spaces with hyphens
    slug = title.lower().replace(' ', '-')

    # Remove all characters except lowercase letters, numbers, and hyphens
    slug = re.sub(r'[^a-z0-9\-]', '', slug)

    # Remove consecutive hyphens (if punctuation caused them)
    slug = re.sub(r'-+', '-', slug).strip('-')

    return slug


def url_safe_title(title: str) -> str:
    """
    Create a lowercase, hyphenated, percent-encoded URL-safe slug from a title.
    Leaves hyphens unescaped but encodes other special characters.
    """
    # Replace spaces with hyphens
    slug = title.lower().replace(' ', '-')

    # Percent-encode everything except hyphens
    return quote(slug, safe='-')


# Optional: demo usage
if __name__ == '__main__':
    examples = [
        "Overview of Security-Orchestration, Automation, and Response (SOAR)",
        "Privacy-preserving: k-anonymity, l-diversity, & t-closeness!",
        "BUILDING UAV SYSTEMS: A.I. & BLOCKCHAIN APPROACHES"
    ]

    for t in examples:
        print("\nOriginal:       ", t)
        print("Slugified:      ", slugify_title(t))
        print("URL-safe title: ", url_safe_title(t))
