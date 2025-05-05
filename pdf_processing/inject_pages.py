def inject_pages_into_articles(articles_data, pages_data):
    if len(articles_data) != len(pages_data):
        raise ValueError(f"Кількість статей ({len(articles_data)}) не збігається з кількістю записів сторінок у PDF ({len(pages_data)})")

    updated_articles = []
    for i, article in enumerate(articles_data):
        updated = (
            article[0],  # english_title
            article[1],  # ukrainian_title
            article[2],  # authors
            (pages_data[i]["start_page"], pages_data[i]["end_page"]),
            article[4],  # references
            article[5],  # abstract
        )
        updated_articles.append(updated)

    return updated_articles

